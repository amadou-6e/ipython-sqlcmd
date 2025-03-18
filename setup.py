from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ipython-sqlcmd",
    version="0.1.4",
    author="Amadou Wolfgang Cisse",
    author_email="amadou.6e@googelmail.com",
    description="SQL Command Magic for IPython",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tensor-works/ipython-sqlcmd",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Framework :: IPython",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Database",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.7",
    install_requires=[
        "ipython>=7.0.0",
        "pandas>=1.0.0",
    ],
    entry_points={
        "ipython_magic": ["sqlcmd=sqlcmd:load_ipython_extension"],
    },
    keywords="ipython, jupyter, sql, sqlcmd, magic",
)
