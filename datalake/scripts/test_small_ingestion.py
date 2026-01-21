#!/usr/bin/env python3
"""
Small-scale test ingestion for E-stat data lake

Tests the complete pipeline with a single dataset from the population domain.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add project root to PYTHONPATH
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from datalake.dataset_registry import DatasetRegistry
from datalake.dataset_selector import DatasetSelector
from datalake.ingestion_orchestrator import IngestionOrchestrator
from datalake.dataset_fetcher import DatasetFetcher
from datalake.data_transformer import DataTransformer
from datalake.data_validator import DataValidator
from datalake.iceberg_loader import IcebergLoader
from datalake.status_monitor import StatusMonitor
from datalake.report_generator import ReportGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """
    Run small-scale test ingestion
    """
    print("\n" + "="*60)
    print("E-STAT DATA LAKE - SMALL SCALE TEST")
    print("="*60 + "\n")
    
    try:
        # Initialize components
        logger.info("Initializing components...")
        registry = DatasetRegistry('datalake/config/dataset_config.yaml')
        
        # Check if we have datasets in registry
        all_datasets = registry.get_all_datasets()
        logger.info(f"Found {len(all_datasets)} datasets in registry")
        
        if not all_datasets:
            logger.info("Registry is empty. Using existing dataset ID for test...")
            # Use a known dataset ID for testing
            test_dataset_id = "0003458339"  # 人口推計
            
            registry.add_dataset(
                dataset_id=test_dataset_id,
                dataset_name="人口推計（令和2年国勢調査基準）",
                domain="population",
                priority=10
            )
            registry.save()
            all_datasets = registry.get_all_datasets()
        
        # Get pending datasets
        pending = [ds for ds in all_datasets if ds.status == 'pending']
        
        if not pending:
            logger.info("No pending datasets. Using first dataset for test...")
            test_dataset_id = all_datasets[0].dataset_id
        else:
            test_dataset_id = pending[0].dataset_id
        
        logger.info(f"Testing with dataset: {test_dataset_id}")
        
        # Initialize pipeline components with MCP functions
        # For now, we'll use None and let the components handle MCP calls internally
        fetcher = DatasetFetcher(mcp_fetch_function=None)
        transformer = DataTransformer(mcp_transform_function=None)
        validator = DataValidator(mcp_validate_function=None)
        loader = IcebergLoader(mcp_load_function=None, mcp_create_table_function=None)
        
        orchestrator = IngestionOrchestrator(
            registry=registry,
            fetcher=fetcher,
            transformer=transformer,
            validator=validator,
            loader=loader,
            max_concurrent=1
        )
        
        # Run ingestion for single dataset
        logger.info("Starting ingestion...")
        result = await orchestrator.ingest_dataset(test_dataset_id)
        
        # Display results
        print("\n" + "="*60)
        print("INGESTION RESULT")
        print("="*60)
        print(f"Dataset ID: {test_dataset_id}")
        print(f"Status: {result.get('status', 'unknown')}")
        
        if result.get('status') == 'success':
            print(f"✓ Ingestion completed successfully")
            print(f"  - Fetch time: {result.get('fetch_time', 0):.2f}s")
            print(f"  - Transform time: {result.get('transform_time', 0):.2f}s")
            print(f"  - Validation time: {result.get('validation_time', 0):.2f}s")
            print(f"  - Load time: {result.get('load_time', 0):.2f}s")
            print(f"  - Total time: {result.get('total_time', 0):.2f}s")
        else:
            print(f"✗ Ingestion failed")
            print(f"  - Error: {result.get('error', 'Unknown error')}")
        
        print("="*60 + "\n")
        
        # Display progress
        status_monitor = StatusMonitor(registry)
        progress = status_monitor.get_ingestion_progress()
        
        print("OVERALL PROGRESS")
        print("="*60)
        print(f"Total Datasets: {progress['total_datasets']}")
        print(f"Completed: {progress['completed_count']}")
        print(f"Failed: {progress['failed_count']}")
        print(f"Success Rate: {progress['success_rate']:.1%}")
        print("="*60 + "\n")
        
        return 0 if result.get('status') == 'success' else 1
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        print(f"\n✗ Test failed: {e}\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
