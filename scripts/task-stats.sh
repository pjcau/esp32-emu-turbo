#!/usr/bin/env bash
# Task Stats — analyze task-times.csv to find slowest and most frequent targets
# Usage: scripts/task-stats.sh [--top N]

set -euo pipefail

LOG_FILE="$(dirname "$0")/../logs/task-times.csv"

if [ ! -f "$LOG_FILE" ]; then
    echo "No timing data yet. Run 'make <target>' to start collecting."
    exit 0
fi

TOP=${1:-10}
TOTAL=$(tail -n +2 "$LOG_FILE" | wc -l | tr -d ' ')

echo "═══════════════════════════════════════════════════════════════"
echo "  TASK PERFORMANCE REPORT  (${TOTAL} runs logged)"
echo "═══════════════════════════════════════════════════════════════"
echo ""

echo "── TOP ${TOP} SLOWEST (avg seconds) ──────────────────────────"
echo ""
printf "  %-25s %8s %8s %8s %5s\n" "TARGET" "AVG" "MAX" "MIN" "RUNS"
printf "  %-25s %8s %8s %8s %5s\n" "-------------------------" "--------" "--------" "--------" "-----"
tail -n +2 "$LOG_FILE" | awk -F',' '{
    target=$2; dur=$3
    count[target]++
    sum[target]+=dur
    if (!(target in max) || dur > max[target]) max[target]=dur
    if (!(target in min) || dur < min[target]) min[target]=dur
}
END {
    for (t in count) {
        avg = sum[t]/count[t]
        printf "  %-25s %8.2f %8.2f %8.2f %5d\n", t, avg, max[t], min[t], count[t]
    }
}' | sort -t' ' -k2 -rn | head -"$TOP"

echo ""
echo "── TOP ${TOP} MOST FREQUENT ──────────────────────────────────"
echo ""
printf "  %-25s %5s %10s %8s\n" "TARGET" "RUNS" "TOTAL_SEC" "FAIL%"
printf "  %-25s %5s %10s %8s\n" "-------------------------" "-----" "----------" "--------"
tail -n +2 "$LOG_FILE" | awk -F',' '{
    target=$2; dur=$3; code=$4
    count[target]++
    sum[target]+=dur
    if (code != 0) fails[target]++
}
END {
    for (t in count) {
        fail_pct = (t in fails) ? (fails[t]/count[t]*100) : 0
        printf "  %-25s %5d %10.1f %7.1f%%\n", t, count[t], sum[t], fail_pct
    }
}' | sort -t' ' -k2 -rn | head -"$TOP"

echo ""
echo "── FAILURE HOTSPOTS ──────────────────────────────────────────"
echo ""
FAILURES=$(tail -n +2 "$LOG_FILE" | awk -F',' '$4 != 0' | wc -l | tr -d ' ')
if [ "$FAILURES" -eq 0 ]; then
    echo "  No failures recorded."
else
    printf "  %-25s %5s %8s\n" "TARGET" "FAILS" "LAST"
    printf "  %-25s %5s %8s\n" "-------------------------" "-----" "--------"
    tail -n +2 "$LOG_FILE" | awk -F',' '$4 != 0 {
        count[$2]++
        last[$2]=$1
    }
    END {
        for (t in count) printf "  %-25s %5d %s\n", t, count[t], last[t]
    }' | sort -t' ' -k2 -rn
fi

echo ""
echo "── TREND (last 7 days) ───────────────────────────────────────"
echo ""
printf "  %-12s %5s %10s %8s\n" "DATE" "RUNS" "TOTAL_SEC" "AVG_SEC"
printf "  %-12s %5s %10s %8s\n" "------------" "-----" "----------" "--------"
tail -n +2 "$LOG_FILE" | awk -F'[,T]' '{
    day=$1; dur=$3
    count[day]++
    sum[day]+=dur
}
END {
    for (d in count) days[++n]=d
    # Simple insertion sort (macOS awk lacks asorti)
    for (i=2; i<=n; i++) {
        key=days[i]
        j=i-1
        while (j>0 && days[j]>key) { days[j+1]=days[j]; j-- }
        days[j+1]=key
    }
    start = (n > 7) ? n-6 : 1
    for (i=start; i<=n; i++) {
        d=days[i]
        printf "  %-12s %5d %10.1f %8.2f\n", d, count[d], sum[d], sum[d]/count[d]
    }
}'

echo ""
echo "Raw data: $LOG_FILE"
echo "═══════════════════════════════════════════════════════════════"
