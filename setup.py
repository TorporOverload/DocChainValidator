from setuptools import setup, find_packages

setup(
    name="doc-validator",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'cryptography',
        'PyPDF2'
    ]
)
