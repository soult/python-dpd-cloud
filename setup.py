#!/usr/bin/env python
# encoding=utf-8

from distutils.core import setup

setup(
    name="python-dpd-cloud",
    version="0.1.0a1",
    description="Python3 library for interacting with DPD cloud as a registered customer",
    long_description="A Python3 library for interacting with the DPD Cloud Web application. It supports creating new shipments. NB: This is not a shipment tracking library - it requires an account with DPD.",
    author="David Triendl",
    author_email="david@triendl.name",
    packages=["dpd_cloud"],
    install_requires=["requests>=2.0.0"],
)
