#!/usr/bin/env python3
"""
Test E-stat API connectivity and response times
"""

import os
import requests
import time
from datetime import datetime

def test_api_connection():
    """Test basic API connectivity"""
    print("\n" + "="*70)
    print("E-STAT API CONNECTION TEST")
    print("="*70)
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Get API key
    app_id = os.environ.get('ESTAT_APP_ID')
    if not app_id:
        print("❌ ESTAT_APP_ID environment variable not set")
        return False
    
    print(f"✓ API Key found: {app_id[:10]}...")
    
    # Test 1: Simple search with short keyword
    print("\n" + "-"*70)
    print("Test 1: Simple search (keyword: '人口')")
    print("-"*70)
    
    url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsList"
    params = {
        "appId": app_id,
        "searchWord": "人口",
        "limit": 3
    }
    
    try:
        start_time = time.time()
        response = requests.get(url, params=params, timeout=60)
        elapsed = time.time() - start_time
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Time: {elapsed:.2f} seconds")
        
        if response.status_code == 200:
            data = response.json()
            if "GET_STATS_LIST" in data:
                datalist = data["GET_STATS_LIST"].get("DATALIST_INF", {})
                table_inf = datalist.get("TABLE_INF", [])
                if not isinstance(table_inf, list):
                    table_inf = [table_inf] if table_inf else []
                
                print(f"✓ Results found: {len(table_inf)} datasets")
                if table_inf:
                    print(f"  Sample: {table_inf[0].get('TITLE', {}).get('$', 'N/A')}")
            else:
                print("⚠ No results in response")
        else:
            print(f"❌ Failed with status code: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    # Test 2: Get dataset metadata
    print("\n" + "-"*70)
    print("Test 2: Get dataset metadata (ID: 0000150001)")
    print("-"*70)
    
    url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
    params = {
        "appId": app_id,
        "statsDataId": "0000150001",
        "limit": 1,
        "metaGetFlg": "Y"
    }
    
    try:
        start_time = time.time()
        response = requests.get(url, params=params, timeout=60)
        elapsed = time.time() - start_time
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Time: {elapsed:.2f} seconds")
        
        if response.status_code == 200:
            data = response.json()
            if "GET_STATS_DATA" in data:
                stats_data = data["GET_STATS_DATA"].get("STATISTICAL_DATA", {})
                result_inf = stats_data.get("RESULT_INF", {})
                total_number = result_inf.get("TOTAL_NUMBER", 0)
                
                print(f"✓ Dataset found")
                print(f"  Total records: {total_number}")
            else:
                print("⚠ No data in response")
        else:
            print(f"❌ Failed with status code: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print("✓ All tests passed")
    print("✓ E-stat API is accessible and responding")
    print("="*70 + "\n")
    
    return True

if __name__ == "__main__":
    success = test_api_connection()
    exit(0 if success else 1)
