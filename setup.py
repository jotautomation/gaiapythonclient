import setuptools

'''
IMPORTANT!
Use python 2 to run setuptools. Otherwise this will end up as an package
at PyPi and we want it to be a module.

Commands to publish
python setup.py sdist bdist_wheel
twine upload dist/*

'''

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="gaiaclient",
    version="0.0.25",
    license='MIT License',
    author="JOT Automation Ltd.",
    author_email="rami.rahikkala@jotautomation.com",
    description="Client for JOT Automation gaia machines",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jotautomation/gaiapythonclient",
    py_modules=['gaiaclient'],
    install_requires=['requests'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
