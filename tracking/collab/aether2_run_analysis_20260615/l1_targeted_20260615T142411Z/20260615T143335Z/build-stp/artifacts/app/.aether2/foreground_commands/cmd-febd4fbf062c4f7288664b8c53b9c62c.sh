sh -lc 'cat > /tmp/test.smt2 <<"EOF"
(set-logic QF_BV)
(assert true)
(check-sat)
EOF
env -i PATH=/usr/local/bin:/usr/bin:/bin sh -lc "command -v stp && stp /tmp/test.smt2"'