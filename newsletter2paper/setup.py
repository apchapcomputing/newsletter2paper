from setuptools import setup, find_packages

setup(
    name="newsletter2paper",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click",
        "feedparser",
        "jinja2",
        "boto3",
        "weasyprint",
        "beautifulsoup4",
        "requests",
    ],
    entry_points={
        "console_scripts": [
            "newsletter2paper=newsletter2paper.cli.commands:cli",
        ],
    },
    author="Your Name",
    author_email="your.email@example.com",
    description="A CLI tool to convert newsletters to newspaper-style PDFs",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/newsletter2paper",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Text Processing :: Markup :: HTML",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
)