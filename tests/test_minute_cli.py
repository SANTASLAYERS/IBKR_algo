#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from unittest.mock import MagicMock, patch
import argparse
import asyncio
from datetime import datetime, timezone, timedelta
import io
import sys

from ibapi.contract import Contract

from src.gateway import IBGateway, IBGatewayConfig
from src.minute_data.models import MinuteBar, MinuteBarCollection
from src.minute_data.manager import MinuteBarManager
import gateway_cli  # Import the CLI module


class TestMinuteDataCLI(unittest.TestCase):
    """Test the CLI commands for minute data functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a sample MinuteBarCollection
        self.timestamp1 = datetime(2023, 5, 1, 14, 30, 0, tzinfo=timezone.utc)
        self.timestamp2 = datetime(2023, 5, 1, 14, 31, 0, tzinfo=timezone.utc)
        
        self.bar1 = MinuteBar(
            symbol="AAPL",
            timestamp=self.timestamp1,
            open_price=150.0,
            high_price=151.0,
            low_price=149.5,
            close_price=150.5,
            volume=1000
        )
        
        self.bar2 = MinuteBar(
            symbol="AAPL",
            timestamp=self.timestamp2,
            open_price=150.5,
            high_price=152.0,
            low_price=150.0,
            close_price=151.5,
            volume=1200
        )
        
        self.collection = MinuteBarCollection(
            symbol="AAPL", 
            bars=[self.bar1, self.bar2]
        )
        
        # Mock the gateway and manager
        self.mock_gateway = MagicMock(spec=IBGateway)
        self.mock_manager = MagicMock(spec=MinuteBarManager)
        
        # Set up the gateway to return our mock manager
        self.mock_gateway.minute_bar_manager = self.mock_manager
        
        # Set up the mock manager to return our test data
        async def mock_fetch_minute_bars(*args, **kwargs):
            return self.collection
            
        self.mock_manager.fetch_minute_bars.side_effect = mock_fetch_minute_bars
    
    @patch('gateway_cli.IBGateway')
    @patch('gateway_cli.load_config')
    @patch('gateway_cli.fetch_minute_data')
    @patch('sys.stdout', new_callable=io.StringIO)
    async def test_fetch_minute_data_command(self, mock_stdout, mock_fetch, mock_load_config, mock_gateway_class):
        """Test the CLI command to fetch minute data."""
        # Set up mocks
        mock_gateway_instance = self.mock_gateway
        mock_gateway_class.return_value = mock_gateway_instance
        mock_load_config.return_value = IBGatewayConfig()
        mock_fetch.return_value = True  # Successful fetch
        
        # Create the argument namespace
        args = argparse.Namespace(
            fetch_minutes=True,
            symbol="AAPL",
            duration="1 D",
            bar_size="1 min",
            end_date=None,  # Use default of now
            output_format="csv",
            output_file=None  # Print to stdout
        )
        
        # Call the main function with our args
        await gateway_cli.main(args)
        
        # Assert fetch_minute_data was called with the right parameters
        mock_fetch.assert_called_once()
        call_args, call_kwargs = mock_fetch.call_args
        
        # Verify the arguments
        self.assertEqual(call_args[0], mock_gateway_instance)
        self.assertEqual(call_args[1], args)
    
    @patch('gateway_cli.IBGateway')
    async def test_fetch_minute_data_output_formats(self, mock_gateway_class):
        """Test different output formats for the minute data."""
        # Set up mocks
        mock_gateway_instance = self.mock_gateway
        mock_gateway_class.return_value = mock_gateway_instance
        
        # Test CSV format
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            await gateway_cli.fetch_minute_data(
                gateway=mock_gateway_instance,
                args=argparse.Namespace(
                    symbol="AAPL",
                    duration="1 D",
                    bar_size="1 min",
                    end_date=None,
                    output_format="csv",
                    output_file=None
                )
            )
            
            output = mock_stdout.getvalue()
            # Check CSV header and data rows
            self.assertIn("timestamp,open,high,low,close,volume", output)
            self.assertIn(self.timestamp1.isoformat(), output)
            self.assertIn(self.timestamp2.isoformat(), output)
        
        # Test JSON format
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            await gateway_cli.fetch_minute_data(
                gateway=mock_gateway_instance,
                args=argparse.Namespace(
                    symbol="AAPL",
                    duration="1 D",
                    bar_size="1 min",
                    end_date=None,
                    output_format="json",
                    output_file=None
                )
            )
            
            output = mock_stdout.getvalue()
            # Check JSON format
            self.assertIn("\"symbol\": \"AAPL\"", output)
            self.assertIn("\"bars\": [", output)
    
    @patch('gateway_cli.IBGateway')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    async def test_fetch_minute_data_file_output(self, mock_file, mock_gateway_class):
        """Test writing minute data to file."""
        # Set up mocks
        mock_gateway_instance = self.mock_gateway
        mock_gateway_class.return_value = mock_gateway_instance
        
        # Test writing to file
        await gateway_cli.fetch_minute_data(
            gateway=mock_gateway_instance,
            args=argparse.Namespace(
                symbol="AAPL",
                duration="1 D",
                bar_size="1 min",
                end_date=None,
                output_format="csv",
                output_file="test_output.csv"
            )
        )
        
        # Check that file was opened for writing
        mock_file.assert_called_once_with("test_output.csv", "w")
        
        # Check that write was called with CSV content
        handle = mock_file()
        handle.write.assert_called()
        
        # Extract what was written
        written_content = ''.join(call[0][0] for call in handle.write.call_args_list)
        
        # Verify the content
        self.assertIn("timestamp,open,high,low,close,volume", written_content)
    
    @patch('gateway_cli.IBGateway')
    async def test_fetch_minute_data_error_handling(self, mock_gateway_class):
        """Test error handling in minute data fetching."""
        # Set up mocks
        mock_gateway_instance = self.mock_gateway
        mock_gateway_class.return_value = mock_gateway_instance
        
        # Make the fetch operation raise an exception
        self.mock_manager.fetch_minute_bars.side_effect = Exception("API error")
        
        # Test error handling
        with patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
            result = await gateway_cli.fetch_minute_data(
                gateway=mock_gateway_instance,
                args=argparse.Namespace(
                    symbol="AAPL",
                    duration="1 D",
                    bar_size="1 min",
                    end_date=None,
                    output_format="csv",
                    output_file=None
                )
            )
            
            # Check the operation returns False on error
            self.assertFalse(result)
            
            # Check error message was written to stderr
            error_output = mock_stderr.getvalue()
            self.assertIn("API error", error_output)
    
    def test_cli_argument_parsing(self):
        """Test the argument parsing for minute data commands."""
        # A convenience method to set up the parser
        def parse_args(args_list):
            parser = argparse.ArgumentParser()
            gateway_cli.add_minute_data_arguments(parser)
            return parser.parse_args(args_list)

        # Test basic usage
        args = parse_args(['--fetch-minutes', 'AAPL'])
        self.assertEqual(args.fetch_minutes, 'AAPL')

        # Test with options
        args = parse_args([
            '--fetch-minutes', 'AAPL',
            '--duration', '2 D',
            '--bar-size', '5 mins',
            '--output-format', 'json',
            '--output-file', 'output.json'
        ])

        self.assertEqual(args.duration, '2 D')
        self.assertEqual(args.bar_size, '5 mins')
        self.assertEqual(args.output_format, 'json')
        self.assertEqual(args.output_file, 'output.json')


if __name__ == "__main__":
    unittest.main()