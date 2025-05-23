# Examples

This directory contains usage examples and demonstrations for the IBKR Trading Framework.

## Main Examples

- **`buy_aapl_insync.py`** - Example AAPL trading script using ib_insync
- **`buy_aapl_test.py`** - AAPL trading test script
- **`minimal_position_test.py`** - Simple position querying example
- **`order_ibkr_integration_demo.py`** - Order management integration demo
- **`order_management_demo.py`** - Order lifecycle management example
- **`position_management_demo.py`** - Position tracking example
- **`simple_position_test.py`** - Basic position test

## Legacy Tests (`legacy_tests/`)

Historical test scripts that have been superseded by the modern pytest test suite but kept for reference:

- Connection tests: `check_tws_connection.py`, `simple_connection_test.py`, `simple_tws_test.py`
- Direct API tests: `simple_direct_test.py`, `simple_fixed_test.py`
- Position tests: `simple_position_test.py`, `test_tws_connection.py`
- Test runners: `run_*.py` scripts
- Mock tests: `tws_mock_test.py`

## Debugging (`debugging/`)

Debug scripts for troubleshooting specific issues:

- **`debug_iborder.py`** - Debug IB order creation
- **`debug_order_test.py`** - Debug order submission

## Usage

For new development, prefer using the examples in the main directory. The legacy tests are primarily for understanding how the system evolved and for troubleshooting specific legacy issues.

Most functionality is now properly tested in the `tests/` directory with pytest.