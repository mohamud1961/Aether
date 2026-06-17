sh -lc 'export PATH=/app/stp/install/bin:$PATH; LD_LIBRARY_PATH=/app/stp/install/lib stp <<"EOF"
(set-logic QF_BV)
(assert true)
(check-sat)
EOF'