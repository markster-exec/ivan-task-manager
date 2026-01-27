"""CLI package setup."""

from setuptools import setup, find_packages

setup(
    name="ivan-cli",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "httpx>=0.24",
        "rich>=13.0",
    ],
    entry_points={
        "console_scripts": [
            "ivan=ivan:cli",
        ],
    },
    python_requires=">=3.9",
)
