#!/usr/bin/env python3
"""
E-stat Data Lake Main Entry Point

Complete data lake construction process for 33 E-stat datasets across 11 domains.
Orchestrates data fetching, transformation, validation, and loading to Iceberg tables.
"""

import os
import sys
import argparse
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List

# Add project root to PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datalake.dataset_registry import DatasetRegistry
from datalake.dataset_fetcher import DatasetFetcher
from datalake.data_transformer import DataTransformer
from datalake.data_validator import DataValidator
from datalake.iceberg_loader import IcebergLoader
from datalake.ingestion_orchestrator import IngestionOrchestrator
from datalake.report_generator import ReportGenerator
from datalake.status_monitor import StatusMonitor
from datalake.config_loader import ConfigLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/datalake_ingestion.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def parse_arguments():
    """
    Parse command line arguments
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='E-stat Data Lake Construction Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full ingestion with default settings
  python datalake/main.py
  
  # Run with custom concurrency
  python datalake/main.py --max-concurrent 10
  
  # Resume from failures
  python datalake/main.py --resume
  
  # Process specific domains only
  python datalake/main.py --domain population economy
  
  # Dry run to see what would be processed
  python datalake/main.py --dry-run
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='datalake/config/datalake_config.yaml',
        help='Path to configuration file (default: datalake/config/datalake_config.yaml)'
    )
    
    parser.add_argument(
        '--max-concurrent',
        type=int,
        default=5,
        help='Maximum concurrent dataset processing (default: 5)'
    )
    
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from last successful stage for failed datasets'
    )
    
    parser.add_argument(
        '--domain',
        type=str,
        nargs='+',
        help='Process specific domains only (e.g., population economy)'
    )
    
    parser.add_argument(
        '--dataset-id',
        type=str,
        nargs='+',
        help='Process specific dataset IDs only'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be processed without actually processing'
    )
    
    parser.add_argument(
        '--report-format',
        type=str,
        choices=['json', 'markdown', 'html'],
        default='markdown',
        help='Final report format (default: markdown)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    return parser.parse_args()


def load_configuration(config_path: str):
    """
    Load configuration from file
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    logger.info(f"Loading configuration from {config_path}")
    
    config_loader = ConfigLoader(config_path)
    config = config_loader.load()
    
    logger.info("Configuration loaded successfully")
    return config


def initialize_components(config, max_concurrent: int):
    """
    Initialize all pipeline components
    
    Args:
        config: Configuration dictionary
        max_concurrent: Maximum concurrent processing
        
    Returns:
        Tuple of (registry, orchestrator, report_generator, status_monitor)
    """
    logger.info("Initializing pipeline components...")
    
    # Initialize Dataset Registry
    registry_path = config.get('registry_path', 'datalake/config/dataset_config.yaml')
    registry = DatasetRegistry(registry_path)
    
    # Initialize pipeline components
    fetcher = DatasetFetcher()
    transformer = DataTransformer()
    validator = DataValidator()
    loader = IcebergLoader()
    
    # Initialize orchestrator
    orchestrator = IngestionOrchestrator(
        registry=registry,
        fetcher=fetcher,
        transformer=transformer,
        validator=validator,
        loader=loader,
        max_concurrent=max_concurrent
    )
    
    # Initialize monitoring and reporting
    status_monitor = StatusMonitor(registry)
    report_generator = ReportGenerator(registry)
    
    logger.info("All components initialized successfully")
    
    return registry, orchestrator, report_generator, status_monitor


def filter_datasets(registry: DatasetRegistry, 
                   domains: Optional[List[str]] = None,
                   dataset_ids: Optional[List[str]] = None) -> List[str]:
    """
    Filter datasets based on criteria
    
    Args:
        registry: Dataset registry
        domains: List of domains to filter by
        dataset_ids: List of dataset IDs to filter by
        
    Returns:
        List of dataset IDs to process
    """
    all_datasets = registry.get_all_datasets()
    
    if dataset_ids:
        # Filter by specific dataset IDs
        filtered = [ds.id for ds in all_datasets if ds.id in dataset_ids]
        logger.info(f"Filtered to {len(filtered)} datasets by ID")
        return filtered
    
    if domains:
        # Filter by domains
        filtered = [ds.id for ds in all_datasets if ds.domain in domains]
        logger.info(f"Filtered to {len(filtered)} datasets by domain")
        return filtered
    
    # Return all datasets
    all_ids = [ds.id for ds in all_datasets]
    logger.info(f"Processing all {len(all_ids)} datasets")
    return all_ids


async def run_ingestion(orchestrator: IngestionOrchestrator,
                       dataset_ids: List[str],
                       resume: bool = False,
                       dry_run: bool = False):
    """
    Run the ingestion pipeline
    
    Args:
        orchestrator: Ingestion orchestrator
        dataset_ids: List of dataset IDs to process
        resume: Resume from last successful stage
        dry_run: Show what would be processed without processing
        
    Returns:
        Ingestion results
    """
    if dry_run:
        logger.info("DRY RUN MODE - No actual processing will occur")
        logger.info(f"Would process {len(dataset_ids)} datasets:")
        for dataset_id in dataset_ids:
            logger.info(f"  - {dataset_id}")
        return []
    
    logger.info(f"Starting ingestion of {len(dataset_ids)} datasets")
    logger.info(f"Resume mode: {'enabled' if resume else 'disabled'}")
    
    # Run batch ingestion
    results = await orchestrator.ingest_batch(dataset_ids, resume=resume)
    
    return results


def display_progress(status_monitor: StatusMonitor):
    """
    Display ingestion progress
    
    Args:
        status_monitor: Status monitor
    """
    progress = status_monitor.get_ingestion_progress()
    
    print("\n" + "="*60)
    print("INGESTION PROGRESS")
    print("="*60)
    print(f"Total Datasets: {progress['total_datasets']}")
    print(f"Completed: {progress['completed_count']}")
    print(f"Failed: {progress['failed_count']}")
    print(f"In Progress: {progress['in_progress_count']}")
    print(f"Pending: {progress['pending_count']}")
    print(f"Success Rate: {progress['success_rate']:.1%}")
    print("="*60 + "\n")


def generate_and_display_report(report_generator: ReportGenerator,
                                orchestrator: IngestionOrchestrator,
                                report_format: str):
    """
    Generate and display final report
    
    Args:
        report_generator: Report generator
        orchestrator: Ingestion orchestrator
        report_format: Report format (json, markdown, html)
    """
    logger.info("Generating final report...")
    
    # Get final report from orchestrator
    final_report = orchestrator.generate_final_report()
    
    # Generate formatted report
    if report_format == 'json':
        report_content = report_generator.generate_json_report(final_report)
        print("\n" + report_content)
    elif report_format == 'markdown':
        report_content = report_generator.generate_markdown_report(final_report)
        print("\n" + report_content)
    elif report_format == 'html':
        report_content = report_generator.generate_html_report(final_report)
        # Save HTML to file
        report_path = f"reports/ingestion_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, 'w') as f:
            f.write(report_content)
        logger.info(f"HTML report saved to {report_path}")
    
    # Display summary
    print("\n" + "="*60)
    print("FINAL INGESTION REPORT")
    print("="*60)
    print(f"Total Datasets: {final_report['total_datasets']}")
    print(f"Successful: {final_report['success_count']}")
    print(f"Failed: {final_report['failed_count']}")
    print(f"Success Rate: {final_report['success_rate']:.1%}")
    print(f"Total Processing Time: {final_report['total_processing_time']:.2f}s")
    print(f"Average Time per Dataset: {final_report['average_time_per_dataset']:.2f}s")
    
    if final_report['failed_datasets']:
        print(f"\nFailed Datasets ({len(final_report['failed_datasets'])}):")
        for dataset_id in final_report['failed_datasets']:
            print(f"  - {dataset_id}")
    
    print("="*60 + "\n")


async def main():
    """
    Main entry point for data lake construction
    """
    # Parse command line arguments
    args = parse_arguments()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Display banner
    print("\n" + "="*60)
    print("E-STAT DATA LAKE CONSTRUCTION")
    print("="*60)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Max Concurrent: {args.max_concurrent}")
    print(f"Resume Mode: {'Enabled' if args.resume else 'Disabled'}")
    print(f"Report Format: {args.report_format}")
    print("="*60 + "\n")
    
    try:
        # Load configuration
        config = load_configuration(args.config)
        
        # Initialize components
        registry, orchestrator, report_generator, status_monitor = initialize_components(
            config, args.max_concurrent
        )
        
        # Filter datasets
        dataset_ids = filter_datasets(registry, args.domain, args.dataset_id)
        
        if not dataset_ids:
            logger.warning("No datasets to process")
            return 1
        
        # Run ingestion
        results = await run_ingestion(
            orchestrator, dataset_ids, args.resume, args.dry_run
        )
        
        if args.dry_run:
            return 0
        
        # Display progress
        display_progress(status_monitor)
        
        # Generate and display final report
        generate_and_display_report(report_generator, orchestrator, args.report_format)
        
        # Determine exit code
        final_report = orchestrator.generate_final_report()
        exit_code = 0 if final_report['failed_count'] == 0 else 1
        
        print(f"\nEnd Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Exit Code: {exit_code}\n")
        
        return exit_code
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Fatal error occurred: {e}\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
