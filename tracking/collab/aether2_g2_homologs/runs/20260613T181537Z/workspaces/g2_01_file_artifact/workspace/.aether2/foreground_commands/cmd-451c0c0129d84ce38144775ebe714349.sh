printf 'status: ready
' > report.txt && printf 'wrote:%s\n' "$(cat report.txt)" && wc -c report.txt