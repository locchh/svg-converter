from setuptools import setup, find_packages

setup(
    name="svg-converter",
    version="1.0.0",
    description="Convert raster images (JPEG, PNG, BMP, GIF, TIFF, WEBP, ...) to SVG",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "Pillow>=10.0.0",
        "numpy>=1.24.0",
        "rich>=13.0.0",
        "click>=8.1.0",
    ],
    extras_require={
        "trace": ["potrace>=0.1.3"],
        "dev": ["pytest>=7.0.0"],
    },
    entry_points={
        "console_scripts": [
            "svg-converter=svg_converter.cli:main",
        ],
    },
)
