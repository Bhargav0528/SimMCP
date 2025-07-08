from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="simmcp",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A Python package for [brief description]",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/simmcp",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.7",
    install_requires=[
        # Add your project's dependencies here
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "black>=21.5b2",
            "isort>=5.8.0",
            "mypy>=0.812",
            "flake8>=3.9.0",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent",
    ],
)
