#!/bin/bash
# profsym.sh <log>: MAMESAMPLE lines of a MAMEPROF run, summed per function
X=$(mktemp -d)
R="$(cd "$(dirname "$0")/../../retro-go" && pwd)"
grep MAMESAMPLE $1 | grep -v total > $X/samples.txt
awk '{print "0x"$2}' $X/samples.txt > $R/.samples_addr.txt
cd "$R/.." && timeout 300 docker compose -f docker-compose.retro-go.yml run --rm retro-go-build sh -c 'xtensa-esp32s3-elf-addr2line -f -e mame-go/build/mame-go.elf $(cat .samples_addr.txt) > .samples_sym.txt' >/dev/null 2>&1
paste <(awk '{print $4}' $X/samples.txt) <(awk 'NR%2==1' $R/.samples_sym.txt) | awk '{a[$2]+=$1; t+=$1} END {for (k in a) printf "%6.2f %s\n", a[k], k; printf "%6.2f (sum of top 100 slices)\n", t}' | sort -rn | head -${2:-25}
rm -f $R/.samples_addr.txt
