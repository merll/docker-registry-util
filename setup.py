import os

from distutils.spawn import find_executable
from setuptools import setup, find_packages

from docker_registry_util import __version__


def include_readme():
    try:
        import pandoc
    except ImportError:
        return ''
    pandoc.core.PANDOC_PATH = find_executable('pandoc')
    readme_file = os.path.join(os.path.dirname(__file__), 'README.md')
    doc = pandoc.Document()
    with open(readme_file, 'r') as rf:
        doc.markdown = rf.read().encode()
        return doc.rst.decode()


setup(
    name='docker-registry-util',
    version=__version__,
    packages=find_packages(),
    install_requires=['setuptools', 'requests'],
    url='https://github.com/merll/docker-registry-util',
    license='MIT',
    author='Matthias Erll',
    author_email='matthias@erll.de',
    description='Search and cleanup on Docker Registry v2.',
    long_description=include_readme(),
    platforms=['OS Independent'],
    keywords=['docker', 'registry', 'query', 'cleanup'],
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Build Tools',
        'Topic :: System :: Software Distribution',
        'Development Status :: 5 - Production/Stable',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    entry_points={
        'console_scripts': [
            'dregutil = docker_registry_util.cli:main',
        ],
    },
    include_package_data=True,
)
