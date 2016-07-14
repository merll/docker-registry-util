from setuptools import setup, find_packages

from docker_registry_util import __version__


setup(
    name='docker-registry-util',
    version=__version__,
    packages=find_packages(),
    install_requires=['setuptools', 'requests'],
    url='',
    license='MIT',
    author='Matthias Erll',
    author_email='matthias@erll.de',
    description='Search and cleanup on Docker Registry v2.',
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
