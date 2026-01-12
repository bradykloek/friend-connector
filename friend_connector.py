import sqlite3
from datetime import datetime, date
import typer
import enum
import rich
import os
from pathlib import Path

class Medium(str, enum.Enum):
    meet = "meet"
    call = "call"
    talk = "talk"
    text = "text"

class Table(str, enum.Enum):
    friends = "friends"
    contacts = "contacts"

past_tense = {
    "meet": "met",
    "call": "called",
    "talk": "talked",
    "text": "texted"
}

DB_NAME = Path(__file__).resolve().parent / "friends.db"

def get_db():
    db = sqlite3.connect(DB_NAME)
    db.execute("PRAGMA foreign_keys = ON;")
    db.row_factory = sqlite3.Row 
    return db

def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS friends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
            );
            """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                friend_id INTEGER NOT NULL REFERENCES friends(id) ON DELETE CASCADE,
                date DATE NOT NULL,
                medium TEXT NOT NULL
            );   
            """)
        
        db.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                friend_id INTEGER NOT NULL REFERENCES friends(id) ON DELETE CASCADE,
                medium TEXT NOT NULL,
                frequency INT NOT NULL,
                PRIMARY KEY (friend_id, medium)
            );   
            """)

app = typer.Typer()

@app.command()
def add(
    name: str = typer.Argument(..., help = "The friend's full name"), 
    ):
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO friends (name) VALUES (?)",
            (name,)
        )
        rich.print(f"Added {name}")

@app.command()
def goal(
    name: str = typer.Argument(..., help = "The friend's full name"), 
    medium: Medium = typer.Argument(..., help = "The medium {meet, call, talk, text} that you intend to contact them by"), 
    frequency: int = typer.Argument(..., help = "How frequently in days you want to contact them. Use 0 to remove a goal")
    ):
    with get_db() as db:
        cursor = db.cursor()
        friend = db.execute("SELECT * FROM friends WHERE name = ?", (name,)).fetchone()

        if not friend:
            rich.print(f"[red]{name} not found in friends[/red]")
            return
        
        if frequency == 0:
            cursor.execute("DELETE FROM goals WHERE friend_id = ? AND medium = ?",
                            (friend["id"], medium.value)
            )
            rich.print(f"Removed goal to {medium.value} {name}")
        else:
            cursor.execute("""
                INSERT INTO goals (friend_id, medium, frequency) VALUES (?, ?, ?)
                ON CONFLICT (friend_id, medium)
                DO UPDATE SET frequency = excluded.frequency
                """,
                (friend["id"], medium.value, frequency)
            )
            rich.print(f"Set goal to {medium.value} {name} every {frequency} days")

@app.command
def rename(
    name: str = typer.Argument(..., help = "The friend's current full name"),
    new_name: str = typer.Argument(..., help="The updated full name")
    ):
        with get_db() as db:
            friend = db.execute("SELECT * FROM friends WHERE name = ?", (name,)).fetchone()
            if not friend:
                rich.print(f"[red]{name} not present in friends table[/red]")
                return
            
            db.execute(f"UPDATE friends SET name = ? WHERE name = ?", (new_name, name))

            if new_name:
                name = new_name
            result = db.execute("SELECT * FROM friends WHERE name = ?", (name,)).fetchone()
            rich.print(f"Renamed {name} to {new_name}")

@app.command()
def contact(
    name: str = typer.Argument(..., help = "The friend's full name"), 
    medium: Medium = typer.Argument(..., help = "The medium {meet, call, talk, text} that you contacted them by"), 
    date: str = typer.Option(default = str(date.today()), help = "The date you contacted them in YYYY-MM-DD (defaults to current date)")
    ):
        with get_db() as db:
            cursor = db.cursor()
            cursor.execute(
                """INSERT INTO contacts (friend_id, medium, date) 
                VALUES ( 
                    (
                        SELECT id FROM friends WHERE name = ?
                    ), 
                    ?, ?)""",
                (name, medium, date)
            )
            rich.print(f"{past_tense[medium.value].capitalize()} with {name} on {date}")

@app.command()
def list():
    medium_hierarchy = """
        CASE {column}
            WHEN 'meet' THEN 4
            WHEN 'call' THEN 3
            WHEN 'talk' THEN 2
            WHEN 'text' THEN 1
            ELSE 0
        END
    """

    query = f"""
    SELECT
        name,
        medium,
        frequency,
        days_since,
        percent_overdue,
        last_valid_contact,
        MAX(percent_overdue) OVER(PARTITION BY id) as most_overdue
    FROM (
        SELECT 
            f.id,
            f.name, 
            g.medium,
            g.frequency,
            MAX(c.date) AS last_valid_contact,
            CAST((julianday('now', 'localtime') - julianday(MAX(c.date))) AS INTEGER) AS days_since,
            100.0 * CAST((julianday('now', 'localtime') - julianday(MAX(c.date))) AS INTEGER) / g.frequency as percent_overdue
        FROM friends f JOIN goals g ON f.id = g.friend_id 
        LEFT JOIN contacts c ON f.id = c.friend_id
            AND ({medium_hierarchy.format(column = "c.medium")}) >= ({medium_hierarchy.format(column = "g.medium")})
        GROUP BY f.id, g.medium
    )
    ORDER BY most_overdue DESC, name, percent_overdue DESC
    """
    
    with get_db() as db:
        rows = db.execute(query).fetchall()

        if not rows:
            typer.echo("Friends list is empty")
            return
        
        prev_name = ""
        medium_history = ""
        
        for row in rows:
            if prev_name != row["name"]:
                if prev_name != "":
                    print_history(prev_name, db)
                    print()
                prev_name = row["name"]
                rich.print(f"[bold]{row["name"]}[/bold]")

            days = int(row["days_since"]) if row["days_since"] is not None else 0
            percent = int(row["percent_overdue"]) if row["percent_overdue"] is not None else 100
            if row["last_valid_contact"] is None:
                last_contact_string = "[red]No contacts logged[/red]"
            else:
                if (percent >= 100):
                    format = "red"
                elif (percent >= 75):
                    format = "dark_orange"
                elif (percent >= 50):
                    format = "gold1"
                else:
                    format = "green"
                last_contact_string = f"{row['last_valid_contact']} ([{format}]{days} days ago: {percent}%[/{format}])"
            
            rich.print(f"   Intend to {row["medium"]} every {row["frequency"]} days: {last_contact_string}")
        print_history(prev_name, db)  

def print_history(name, db):
    medium_history = db.execute("""
                        SELECT GROUP_CONCAT(recents.medium || ": " || recents.most_recent, ", ")
                        FROM (
                            SELECT medium, MAX(date) as most_recent
                            FROM contacts
                            WHERE friend_id = (SELECT id FROM friends WHERE name = ?)
                            GROUP BY medium
                            ORDER BY date DESC
                        ) AS recents
                        """, (name,)).fetchone()[0]
    if medium_history:
        rich.print(f"   [dim]{medium_history}[/dim]")   

init_db()
app()