#!/bin/bash

awk '/^# INSERT kojikamid dup #/ {exit} {print $0}' kojikamid.py

for fn in ../koji/__init__.py ../koji/daemon.py ../koji/util.py
do
    awk '/^# END kojikamid dup #/ {p=0} p {print $0} /^# BEGIN kojikamid dup #/ {p=1}' $fn
done

awk 'p {print $0} /^# INSERT kojikamid dup #/ {p=1}' kojikamid.py
