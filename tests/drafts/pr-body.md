## Summary

This pull request introduces the new `widget-core` module to the example-widget library, providing a foundational interface for dynamic data binding. We have refactored the internal event loop to handle concurrent requests more efficiently without blocking the main thread. Additionally, the configuration schema now supports JSON5 syntax for easier readability during development cycles. These changes lay the groundwork for the upcoming v2.0 release scheduled next quarter.

## What changed

- Updated `widget-core.py` to include the new binding logic.
- Removed deprecated imports from `utils.py`.
- Added type hints to all public functions in the main package
- Fixed a minor logging issue in the error handler

## Testing

```sh
CANARY_CODE make test
```

Run the full test suite to verify that all new bindings work correctly across different operating systems. Ensure that the CI pipeline passes before merging this branch into the main development line.

| Check | Result | Note |
|---|---|---|
| CANARY_CODE | CANARY_CODE | CANARY_CODE |
| CANARY_CODE | CANARY_CODE | CANARY_CODE |
| CANARY_CODE | CANARY_CODE | CANARY_CODE |

Please review the `canary_var` variable usage in the test scripts before deploying. You can find more details about the testing framework [here](https://example.com/canary-docs).

<details>
<summary>CANARY_CODE long log</summary>

The automated build process completed successfully after the third retry attempt. All unit tests passed within the expected time frame for the current workload.
</details>

-- Sent from the made-up example footer
