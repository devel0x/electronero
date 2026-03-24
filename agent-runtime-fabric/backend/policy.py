DEPLOYMENT_TOOLS = {
    "clone_repo",
    "checkout_ref",
    "detect_stack",
    "install_node_deps",
    "install_python_deps",
    "write_env_file",
    "start_process",
    "stop_process",
    "check_port",
    "http_health_check",
    "stream_logs",
    "capture_preview_metadata",
    "export_artifacts",
}

SAFE_CODE_TOOLS = {
    "run_code",
    "install_package",
    "read_file",
    "write_file",
    "list_directory",
    "search_in_files",
    "functions_mapping",
    "bracket_tracker",
    "export_artifact",
    "session_reset",
}

ALLOWED_TOOLS = DEPLOYMENT_TOOLS | SAFE_CODE_TOOLS
