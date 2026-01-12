from setuptools import setup

setup(
    name="friends",
    py_modules=["friend_connector"],
    install_requires=["typer", "rich"],
    entry_points={
        "console_scripts": [
            "friends = friend_connector:app",
        ],
    },
)