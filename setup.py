"""
Setup script for AI Agent Payments SDK.
"""

import os

from setuptools import find_packages, setup


# Read the README file
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()


# Read requirements
def read_requirements():
    req_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    with open(req_path) as f:
        return f.read().splitlines()


setup(
    name="aiagent-payments",
    version="0.0.1-beta",
    author="Chirag Maliwal",
    author_email="Chiragmaliwal1995@gmail.com",
    description="A general-purpose Python SDK for AI agent monetization with subscription and pay-per-use models",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/cmaliwal/aiagent-payments",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Office/Business :: Financial",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.10",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=8.4.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.10.0",
            "black>=25.1.0",
            "flake8>=7.0.0",
            "isort>=6.0.0",
            "mypy>=1.10.0",
            "bandit>=1.8.0",
            "safety>=3.2.0",
            "pre-commit>=4.2.0",
            "build>=1.2.0",
            "twine>=5.1.0",
        ],
        "stripe": [
            "stripe>=12.2.0",
        ],
        "paypal": [
            "paypalrestsdk>=1.13.0",
        ],
        "crypto": [
            "web3>=6.0.0",
            "qrcode>=7.4.0",
            "pillow>=10.0.0",
        ],
        "database": [
            "sqlalchemy>=1.4.0",
            "alembic>=1.7.0",
        ],
        "web": [
            "flask>=2.0.0",
            "fastapi>=0.68.0",
            "uvicorn>=0.15.0",
        ],
        "examples": [
            "crewai>=0.134.0",
            "langgraph>=0.2.0",
            "langchain-core>=0.3.0",
            "langchain>=0.3.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "aiagent-payments=cli.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "aiagent_payments": ["py.typed"],
    },
    keywords=[
        "ai",
        "agent",
        "payments",
        "monetization",
        "subscription",
        "pay-per-use",
        "freemium",
        "billing",
        "usage-tracking",
    ],
    project_urls={
        "Bug Reports": "https://github.com/cmaliwal/aiagent-payments/issues",
        "Source": "https://github.com/cmaliwal/aiagent-payments",
        "Documentation": "https://github.com/cmaliwal/aiagent-payments",
    },
)
