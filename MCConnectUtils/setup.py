from setuptools import setup, find_packages

setup(
    name='MCConnectUtils',  # Replace with your package name
    version='0.1',
    packages=find_packages(),  # Automatically find packages in the directory
    install_requires=[  # List dependencies here
        # 'some_package',
    ],
    include_package_data=True,
    description='some utils',
    long_description_content_type='text/markdown',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
