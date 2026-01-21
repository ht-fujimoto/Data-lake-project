#!/usr/bin/env python3
"""
Load datasets for all 11 domains into E-stat data lake
"""

import json
import time
from datetime import datetime

# Domain configuration (excluding population which is already loaded)
DOMAINS = {
    'economy': '経済センサス',
    'labor': '労働力調査',
    'education': '学校基本調査',
    'health': '医療施設調査',
    'agriculture': '農林業センサス',
    'construction': '建築着工統計',
    'transport': '自動車輸送統計',
    'trade': '商業統計',
    'social_welfare': '社会福祉施設調査',
    'generic': '統計'
}

def main():
    print("\n" + "="*70)
    print("E-STAT DATA LAKE - LOAD ALL DOMAINS")
    print("="*70)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Domains to process: {len(DOMAINS)}")
    print("="*70 + "\n")
    
    results = {
        'success': [],
        'failed': [],
        'skipped': []
    }
    
    for i, (domain, keyword) in enumerate(DOMAINS.items(), 1):
        print(f"\n[{i}/{len(DOMAINS)}] Processing domain: {domain}")
        print(f"Keyword: {keyword}")
        print("-" * 70)
        
        try:
            # Note: This script provides the workflow
            # Actual execution should be done via MCP tools in Kiro
            
            print(f"✓ Domain: {domain}")
            print(f"  1. Search: mcp_estat_datalake_search_estat_data(query='{keyword}')")
            print(f"  2. Fetch: mcp_estat_datalake_fetch_dataset_auto(dataset_id='<id>')")
            print(f"  3. Save: mcp_estat_datalake_save_to_parquet(...)")
            print(f"  4. Load: mcp_estat_datalake_load_to_iceberg(domain='{domain}')")
            
            results['skipped'].append(domain)
            
        except Exception as e:
            print(f"✗ Error processing {domain}: {e}")
            results['failed'].append(domain)
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Total domains: {len(DOMAINS)}")
    print(f"Success: {len(results['success'])}")
    print(f"Failed: {len(results['failed'])}")
    print(f"Skipped: {len(results['skipped'])}")
    print("="*70)
    
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print("""
For each domain, execute the following MCP tools in Kiro:

1. Search for dataset:
   mcp_estat_datalake_search_estat_data(query="<keyword>", max_results=5)

2. Fetch dataset:
   mcp_estat_datalake_fetch_dataset_auto(dataset_id="<id>", save_to_s3=True)

3. Save to Parquet:
   mcp_estat_datalake_save_to_parquet(
       s3_input_path="<s3_path_from_step_2>",
       s3_output_path="s3://estat-iceberg-datalake/parquet/<domain>/<id>.parquet",
       domain="<domain>",
       dataset_id="<id>"
   )

4. Load to Iceberg:
   mcp_estat_datalake_load_to_iceberg(
       domain="<domain>",
       s3_parquet_path="<s3_path_from_step_3>",
       create_if_not_exists=True
   )
    """)
    print("="*70 + "\n")
    
    print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

if __name__ == "__main__":
    main()
