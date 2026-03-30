from setuptools import setup

package_name = 'px_pir'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='px_dev',
    maintainer_email='px_dev@example.com',
    description='PIR sensor watch node for SeamlessTrack-PX (Telemetrix)',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'pir_watch_node = px_pir.pir_watch_node:main',
        ],
    },
)
