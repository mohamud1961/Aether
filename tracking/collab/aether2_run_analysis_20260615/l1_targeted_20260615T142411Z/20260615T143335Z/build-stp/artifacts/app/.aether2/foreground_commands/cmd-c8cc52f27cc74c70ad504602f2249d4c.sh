sh -lc 'export PATH=/app/stp/install/bin:$PATH; command -v stp; stp <<"EOF"
(set-logic QF_BV)
(assert true)
(check-sat)
EOF'