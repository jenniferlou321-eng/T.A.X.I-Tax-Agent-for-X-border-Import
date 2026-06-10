from setuptools import setup, find_packages

setup(
    name="tax-agent",
    version="0.1.0",
    packages=find_packages(where=".", include=["backend*"]),
    package_dir={"": "."},
    python_requires=">=3.9",
)