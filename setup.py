from setuptools import setup, find_packages

# README für PyPI laden
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Requirements laden
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="mp3-tagger",
    version="1.0.0",
    author="MP3 Tagger Team",
    author_email="contact@mp3tagger.dev",
    description="Intelligentes Metadaten-Anreicherungstool für MP3-Dateien",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourname/mp3-tagger",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Utilities",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "mp3-tagger=main:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["config/*.yaml"],
    },
)
