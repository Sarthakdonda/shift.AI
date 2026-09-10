# Workspace preferences

- Stop only servers you started specifically for testing, and verify their test ports are closed. Leave the user's normal frontend and backend servers (typically ports 3000 and 8000, including VS Code terminal sessions) running. Never terminate them during test cleanup.
- Keep verification builds isolated from running development servers: set SHIFT_TEST_BUILD_DIR to a separate test/build directory rather than writing to the normal `.next` directory.
- Preserve project files and saved projects. Remove temporary testing artifacts when verification is finished.
