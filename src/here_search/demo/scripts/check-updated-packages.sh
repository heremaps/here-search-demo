#!/bin/bash

pur_out=$(mktemp)
diff_out=$(mktemp)
SED_CMD=$(command -v gsed || echo "sed")

for f in requirements/*; do
  pur -r $f --dry-run --nonzero-exit-code --skip pur | tee $pur_out
  $SED_CMD -i -e '/^==>/d' -e '$ d' $pur_out
  diff -aw $f $pur_out &>$diff_out
  exit_code=$?

  if [ $exit_code -ne 0 ]; then
    echo '================================='
    echo '>>> detected these differences:'
    cat $diff_out
  fi
done

exit $exit_code
