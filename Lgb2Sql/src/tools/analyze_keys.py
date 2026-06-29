import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from metadata import MetadataManager

mm = MetadataManager()
mm.load('../config/metadata.yaml')

print("=" * 70)
print(" 各表主键(JOIN KEY)清单")
print("=" * 70)

for tbl_name, tbl in sorted(mm.tables.items()):
    jk = tbl.join_key or "NULL"
    pf = tbl.partition_field or "NULL"
    vc = len(tbl.variables)
    print(f"{tbl_name:<55s} -> join_key={jk:<15s} partition={pf:<10s} vars={vc:>4}")

print("=" * 70)
print(f" 总计: {len(mm.tables)} 张表")
print("=" * 70)
