Supported Platforms
===================

We're now supporting Linux systems which have at least python 2.7 for
builders and 3.6 for other components. These versions are minimal (so,
everywhere where is 2.7 support it means 2.7+ *and* 3.0+. Currently it
involves all active Fedoras and RHEL/CentOS 7+.

+-----------+-----+-----+---------+-------+-----+-----+
| Component | Hub | Web | Builder | Utils | Lib | CLI |
+===========+=====+=====+=========+=======+=====+=====+
| Python    | 3.6 | 3.6 | 2.7     | 3.6   | 2.7 | 2.7 |
+-----------+-----+-----+---------+-------+-----+-----+

For database we're supporting RHEL/CentOS 8+. So, it means that
postgresl 10 is still supported, anyway we encourage using at
least PG 12 (``dnf module enable postgresql:12``).  At least some
indices are set up in more efficient way with newer PG
capabilities.
