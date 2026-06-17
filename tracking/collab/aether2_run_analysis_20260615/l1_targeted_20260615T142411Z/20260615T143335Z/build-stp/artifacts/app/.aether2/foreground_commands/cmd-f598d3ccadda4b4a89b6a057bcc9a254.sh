sh -lc 'cat > /usr/local/bin/stp <<"EOF"
#!/bin/sh
exec env LD_LIBRARY_PATH=/app/stp/install/lib /app/stp/install/bin/stp "$@"
EOF
chmod +x /usr/local/bin/stp
command -v stp
stp <<"EOF"
(set-logic QF_BV)
(assert true)
(check-sat)
EOF'