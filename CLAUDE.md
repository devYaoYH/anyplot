# Testing Guidelines

- test names should be informative, e.g. test_some_component_has_desired_outcome
- try to abstract common fixtures when mocking is required
- tests should generally follow the Arrange, Act, Assert format
- make tests more readable by arranging particular values needed for the test within the test itself instead of as an entirely separate helper function far away from the rest of the act and assertion code
- structure functional tests in layers:
  - unit tests that vary arguments and test a particular function
  - integration tests may test the functioning of entire objects at once across multiple functions, tests should specify the expected behavior of the object in question. Where external dependencies are required, these are mostly mocked.
  - end-to-end tests should cover the entire service or across multiple services, for example, actually starting up the server and sending fake data to it, or using playwright for testing the user interface by actually rendering it in a browser.
- data testing should be split into:
  - Behavioural tests should allow users to describe Critical User Journies (CUJs) and specify the expected behavior.
  - Smoke tests roughly fall into the integration tests category, checking whether a single or small cluster of datapoints can flow through the entire app successfully.
  - Load tests should generate and use large synthetic datasets to stress-test the system at SLOs (Service Level Objectives) that the user targets.

# Python Guidelines

- this project uses `uv` for package management, as such, execute scripts and tests with `uv run ...`
- never use inline imports, always import at the top of the file
- do not nest inline functions unless absolutely necessary
- prefer pydantic models and serialization when some structured data is required instead of ad-hoc data classes

# Frontend React Guidelines

- build reusable components
- use websockets and clean them up when requiring streaming data processing between the backend and frontend UI

# Backend Server Guidelines

- always return readable and informative error messages alongside error codes
- for long-running processses, use a streaming processing model and update frontend with execution status in an event-driven model
