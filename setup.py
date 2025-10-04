"""
Setup configuration for Kite Auto-Trading application.
"""

from setuptools import setup, find_packages
import os

# Read the contents of README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Read requirements from requirements.txt
with open('requirements.txt') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="kite-auto-trading",
    version="0.1.0",
    author="Auto-Trading System",
    author_email="developer@example.com",
    description="Automated trading system for Zerodha Kite Connect API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/example/kite-auto-trading",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.19.0",
            "pytest-mock>=3.8.0",
            "pytest-cov>=3.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=0.971",
            "pre-commit>=2.20.0",
        ],
        "database": [
            "SQLAlchemy>=1.4.0",
            "alembic>=1.8.0",
        ],
        "cache": [
            "redis>=4.3.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "kite-auto-trading=kite_auto_trading.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "kite_auto_trading": [
            "config/*.yaml",
            "config/*.json",
        ],
    },
)