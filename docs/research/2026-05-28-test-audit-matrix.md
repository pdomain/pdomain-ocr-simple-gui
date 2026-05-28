# Test Suite Audit Matrix — 2026-05-28

Produced by M1 of the test-suite audit/reorg plan.
Reference plan: `docs/plans/2026-05-28-test-suite-audit-reorg.md`

---

## Backend summary

Backend tests: 190 collected across 24 files (including smoke).

| Reason code | Count |
|---|---|
| ok | 125 |
| no-bad-case | 43 |
| asserts-mock | 18 |
| tautological | 4 |
| duplicate | 0 |

Mock-depth breakdown: none — 128, shallow — 38, deep — 35.

---

## Backend

| Test (path::name) | Module under test | Behavior asserted | Mock depth (none/shallow/deep) | Good state? | Bad state? | Reason code |
|---|---|---|---|---|---|---|
| tests/test_config_route.py::test_config_route_local_not_containerized | routes.config | GET /api/config returns correct fields in local mode | shallow (monkeypatches detect_containerized, `_detect_device`, env var; creates real app) | yes | no | no-bad-case |
| tests/test_config_route.py::test_config_route_managed_containerized | routes.config | GET /api/config returns correct fields in managed/containerized mode | shallow (same) | yes | no | no-bad-case |
| tests/test_container_detect.py::test_dockerenv_marker | runtime.container_detect | .dockerenv file presence → containerized=True | none (uses real tmppath + monkeypatch filesystem attrs) | yes | no | ok |
| tests/test_container_detect.py::test_podman_marker | runtime.container_detect | podman containerenv marker → containerized=True | none | yes | no | ok |
| tests/test_container_detect.py::test_container_env_var | runtime.container_detect | container env var set → containerized=True | none | yes | no | ok |
| tests/test_container_detect.py::test_cgroup_signal | runtime.container_detect | cgroup string with docker → containerized=True | none | yes | no | ok |
| tests/test_container_detect.py::test_none_match | runtime.container_detect | no signals → containerized=False | none | yes (bad=False) | yes (good=True covered by other tests) | ok |
| tests/test_download_route.py::test_download_streams_zip | routes.download | GET download returns 200 zip with files | none (real storage + tmp_path) | yes | no | ok |
| tests/test_download_route.py::test_download_missing_job | routes.download | missing job → 404 | none | no | yes | ok |
| tests/test_download_route.py::test_download_include_text_only | routes.download | ?include=text returns only txt+images | none | yes | no | ok |
| tests/test_download_route.py::test_download_include_json_only | routes.download | ?include=json returns only json+images | none | yes | no | ok |
| tests/test_download_route.py::test_download_include_both_explicit | routes.download | ?include=text,json returns both | none | yes | no | ok |
| tests/test_download_route.py::test_download_default_is_both | routes.download | no include param returns both | none | yes | no | ok |
| tests/test_download_route.py::test_download_invalid_include_value | routes.download | invalid include → 400 | none | no | yes | ok |
| tests/test_dynamic_port.py::TestDynamicPortCLI::test_uvicorn_called_with_picked_port | __main__ / bootstrap_spa | uvicorn.run receives port from bootstrap_spa | deep (patches bootstrap_spa + uvicorn.run + sys.argv) | yes | no | asserts-mock |
| tests/test_dynamic_port.py::TestDynamicPortCLI::test_bootstrap_spa_called_with_expected_kwargs | __main__ / bootstrap_spa | bootstrap_spa receives caller_package, port_env | deep (patches bootstrap_spa + uvicorn.run) | yes | no | asserts-mock |
| tests/test_dynamic_port.py::TestDynamicPortCLI::test_cli_port_flag_overrides_default | __main__ / bootstrap_spa | --port flag forwards to bootstrap_spa as preferred | deep (patches bootstrap_spa + uvicorn.run + sys.argv) | yes | no | no-bad-case |
| tests/test_dynamic_port.py::TestBootstrapSpaImportable::test_bootstrap_spa_is_importable | pdomain_ops.suite.bootstrap_spa | bootstrap_spa is importable and callable | none | yes | no | no-bad-case |
| tests/test_dynamic_port.py::TestBootstrapSpaImportable::test_find_available_port_is_importable | pdomain_ops.suite.find_available_port | find_available_port is importable | none | yes | no | ok |
| tests/test_dynamic_port.py::TestBootstrapSpaImportable::test_find_available_port_returns_int | pdomain_ops.suite.find_available_port | returns int in valid port range | none | yes | no | no-bad-case |
| tests/test_entrypoint.py::TestEntrypoint::test_help_exits_zero | __main__ | --help exits 0 and prints --port/--host | none (subprocess) | yes | no | no-bad-case |
| tests/test_entrypoint.py::TestEntrypoint::test_module_main_importable | __main__ | main() is importable and callable | none | yes | no | no-bad-case |
| tests/test_models.py::TestProjectSpec::test_round_trip_json | models.ProjectSpec | JSON round-trip restores spec | none | yes | no | ok |
| tests/test_models.py::TestProjectSpec::test_defaults | models.ProjectSpec | save_json=False, combined_txt=True defaults | none | yes | no | ok |
| tests/test_models.py::TestProjectSpec::test_engine_literal | models.ProjectSpec | invalid engine raises ValidationError | none | no | yes | ok |
| tests/test_models.py::TestProjectSpec::test_tesseract_engine | models.ProjectSpec | tesseract engine accepted | none | yes | no | ok |
| tests/test_models.py::TestPageResult::test_defaults | models.PageResult | text_preview="", error=None defaults | none | yes | no | ok |
| tests/test_models.py::TestPageResult::test_round_trip | models.PageResult | JSON round-trip restores page result | none | yes | no | ok |
| tests/test_models.py::TestPageResult::test_state_literal | models.PageResult | invalid state raises ValidationError | none | no | yes | ok |
| tests/test_models.py::TestProjectStatus::test_round_trip | models.ProjectStatus | JSON round-trip restores status with pages | none | yes | no | no-bad-case |
| tests/test_models.py::TestAppPrefs::test_defaults | models.AppPrefs | default engine/language/flags/recent correct | none | yes | no | no-bad-case |
| tests/test_models.py::TestAppPrefs::test_round_trip | models.AppPrefs | JSON round-trip restores prefs | none | yes | no | no-bad-case |
| tests/test_output_config.py::test_managed_default | output.config.resolve_output_dir | managed mode resolves to managed_root/job_id | none | yes | no | ok |
| tests/test_output_config.py::test_next_to_source_folder | output.config.resolve_output_dir | next_to_source for folder returns source dir | none | yes | no | ok |
| tests/test_output_config.py::test_next_to_source_rejects_non_folder | output.config.resolve_output_dir | next_to_source on non-folder raises OutputConfigError | none | no | yes | ok |
| tests/test_output_config.py::test_specified_local | output.config.resolve_output_dir | specified mode returns explicit path | none | yes | no | ok |
| tests/test_output_config.py::test_specified_rejected_in_managed | output.config.resolve_output_dir | specified mode in managed raises OutputConfigError | none | no | yes | ok |
| tests/test_pipeline.py::TestExtractWords::test_flattens_word_tree | pipeline.extract_words | word tree flattened to list with text | none | yes | no | ok |
| tests/test_pipeline.py::TestExtractWords::test_bbox_is_xywh_normalized | pipeline.extract_words | bbox converted to x/y/w/h normalized | none | yes | no | no-bad-case |
| tests/test_pipeline.py::TestExtractWords::test_skips_words_without_geometry | pipeline.extract_words | words with null bbox excluded | none | yes (filter works) | yes (only-null case) | ok |
| tests/test_pipeline.py::TestExtractWords::test_empty_for_page_with_no_words | pipeline.extract_words | empty page returns empty list | none | no (edge) | yes (empty) | ok |
| tests/test_pipeline.py::TestBuildSidecarPayload::test_adds_text_width_height_words | pipeline.build_sidecar_payload | sidecar has text, width, height, words with correct shape | none | yes | no | no-bad-case |
| tests/test_pipeline.py::TestBuildSidecarPayload::test_preserves_original_tree | pipeline.build_sidecar_payload | original type/items keys preserved in payload | none | yes | no | no-bad-case |
| tests/test_pipeline.py::TestCollectImages::test_returns_sorted_png_files | pipeline.collect_images | sorted PNG list from directory | none | yes | no | ok |
| tests/test_pipeline.py::TestCollectImages::test_returns_jpg_and_tiff | pipeline.collect_images | JPG/JPEG/TIFF extensions collected | none | yes | no | ok |
| tests/test_pipeline.py::TestCollectImages::test_skips_non_image_files | pipeline.collect_images | non-image files excluded | none | yes | no | ok |
| tests/test_pipeline.py::TestCollectImages::test_accepts_single_file | pipeline.collect_images | single file path returns list with that file in a dir | none | yes | no | ok |
| tests/test_pipeline.py::TestCollectImages::test_returns_empty_for_empty_dir | pipeline.collect_images | empty dir returns [] | none | no (edge) | yes (empty) | ok |
| tests/test_pipeline.py::TestCollectImages::test_returns_empty_for_nonexistent | pipeline.collect_images | nonexistent path returns [] | none | no | yes | ok |
| tests/test_pipeline.py::TestCollectImages::test_accepts_jpeg2000_family | pipeline.collect_images | jp2/j2k/jpf/jpx/jpm collected | none | yes | no | ok |
| tests/test_pipeline.py::TestRunProject::test_calls_run_ocr_batch_for_images | pipeline.run_project | run_ocr_batch called for all images; callbacks fired | shallow (mock dispatcher with real async fn; real storage) | yes | no | ok |
| tests/test_pipeline.py::TestRunProject::test_status_callback_receives_project_status | pipeline.run_project | callback receives ProjectStatus objects | shallow | yes | no | ok |
| tests/test_pipeline.py::TestRunProject::test_run_ocr_batch_request_fields | pipeline.run_project | OcrBatchRequest has correct engine/language/images | shallow | yes | no | ok |
| tests/test_pipeline.py::TestRunProject::test_extracts_text_from_page_dict | pipeline.run_project | extracted text written to .txt sidecar | shallow | yes | no | ok |
| tests/test_pipeline.py::TestRunProject::test_sidecar_carries_text_dims_and_words | pipeline.run_project | sidecar JSON has text/width/height/words shape | shallow | yes | no | ok |
| tests/test_pipeline.py::TestRunProject::test_writes_outputs_into_output_dir | pipeline.run_project | save_json+combined_txt writes correct files to output_dir | shallow | yes | no | ok |
| tests/test_pipeline.py::TestRunProject::test_save_json_false_skips_json_in_output_dir | pipeline.run_project | save_json=False omits .json from output_dir | shallow | yes (txt exists) | yes (no json) | ok |
| tests/test_pipeline.py::TestProgressMessage::test_progress_message_sequence | pipeline.run_project | progress messages emitted in correct order | shallow | yes | no | no-bad-case |
| tests/test_pipeline.py::TestChunkFailureIsolation::test_second_chunk_failure_does_not_abort_first | pipeline.run_project | chunk 2 RuntimeError leaves chunk 1 succeeded, job=failed | shallow | yes (partial success) | yes (failure) | ok |
| tests/test_routes_jobs.py::TestPostJob::test_creates_job | routes.jobs POST /api/jobs | returns 202 with project_id | shallow (per-file async_client fixture, real storage) | yes | no | ok |
| tests/test_routes_jobs.py::TestPostJob::test_created_job_is_retrievable | routes.jobs POST+GET | created job retrievable with canonical state | shallow | yes | no | ok |
| tests/test_routes_jobs.py::TestGetJob::test_404_for_missing | routes.jobs GET /api/jobs/:id | 404 for nonexistent job | shallow | no | yes | ok |
| tests/test_routes_jobs.py::TestGetJob::test_returns_project_status | routes.jobs GET /api/jobs/:id | response has all required status fields incl. name/output_dir | shallow | yes | no | ok |
| tests/test_routes_jobs.py::TestListJobs::test_empty_list | routes.jobs GET /api/jobs | empty list when no jobs | shallow | yes (edge) | no | no-bad-case |
| tests/test_routes_jobs.py::TestListJobs::test_lists_created_jobs | routes.jobs GET /api/jobs | created jobs appear with name enrichment | shallow | yes | no | no-bad-case |
| tests/test_routes_jobs.py::TestDeleteJob::test_delete_removes_job | routes.jobs DELETE /api/jobs/:id | delete removes job; subsequent GET is 404 | shallow | yes | no | ok |
| tests/test_routes_jobs.py::TestDeleteJob::test_delete_missing_is_204 | routes.jobs DELETE /api/jobs/:id | delete nonexistent is 204 no-op | shallow | no (edge) | yes | ok |
| tests/test_routes_jobs.py::TestPipelineIntegration::test_run_project_called_on_post | routes.jobs / pipeline integration | POST triggers run_project with correct spec | deep (patches run_project) | yes | no | asserts-mock |
| tests/test_routes_jobs.py::TestPipelineIntegration::test_job_transitions_to_done_via_mock | routes.jobs / pipeline integration | job state transitions to succeeded via mocked pipeline | deep (patches run_project) | yes | no | asserts-mock |
| tests/test_routes_jobs.py::TestPipelineIntegration::test_dispatcher_passed_to_run_project | routes.jobs / pipeline integration | LocalStageDispatcher instance passed to run_project | deep (patches run_project, captures arg) | yes | no | asserts-mock |
| tests/test_routes_jobs.py::TestPipelineIntegration::test_zero_supported_images_marks_job_failed | routes.jobs / pipeline integration | no supported images → job fails with error message | shallow (real pipeline, real storage) | no | yes | ok |
| tests/test_routes_jobs.py::TestCanonicalJobStates::test_failed_job_returns_failed_not_error | routes.jobs canonical states | state=failed, not legacy 'error' | deep (patches run_project) | no | yes | asserts-mock |
| tests/test_routes_jobs.py::TestCanonicalJobStates::test_succeeded_job_returns_succeeded_not_done | routes.jobs canonical states | state=succeeded, not legacy 'done' | deep (patches run_project) | yes | no | asserts-mock |
| tests/test_routes_jobs.py::TestCanonicalJobStates::test_state_is_always_a_canonical_value | routes.jobs canonical states | state value is in canonical set | shallow | yes | no | no-bad-case |
| tests/test_routes_jobs.py::TestRerunJob::test_rerun_returns_queued_state | routes.jobs POST /api/jobs/:id/rerun | rerun resets to queued state | deep (patches run_project) | yes | no | asserts-mock |
| tests/test_routes_jobs.py::TestRerunJob::test_rerun_resets_pages_to_queued | routes.jobs POST /api/jobs/:id/rerun | all pages reset to queued after rerun | deep (patches run_project) | yes | no | asserts-mock |
| tests/test_routes_jobs.py::TestRerunJob::test_rerun_404_for_missing | routes.jobs POST /api/jobs/:id/rerun | rerun nonexistent project → 404 | shallow | no | yes | ok |
| tests/test_routes_jobs.py::TestRerunJob::test_rerun_triggers_pipeline | routes.jobs POST /api/jobs/:id/rerun | rerun calls run_project with project_id | deep (patches run_project) | yes | no | asserts-mock |
| tests/test_routes_jobs.py::TestUploadIdSource::test_create_job_with_upload | routes.jobs / upload source | POST with upload_id returns 200/202 | shallow (real storage, real upload dir) | yes | no | no-bad-case |
| tests/test_routes_jobs.py::TestOutputModeRoundTrip::test_output_mode_returned_on_get | routes.jobs / output mode | output_mode=managed returned on GET after POST | shallow (real storage) | yes | no | no-bad-case |
| tests/test_routes_jobs.py::TestOutputModeRoundTrip::test_output_mode_absent_for_legacy_jobs | routes.jobs / output mode | legacy job GET returns output_mode=None | shallow | yes | no | no-bad-case |
| tests/test_routes_pages.py::TestGetPage::test_returns_page_response | routes.pages GET /api/pages/:id/:idx | returns correct PageResponse with text/dims | none (real storage, project_with_image fixture) | yes | no | ok |
| tests/test_routes_pages.py::TestGetPage::test_404_for_missing_project | routes.pages GET /api/pages/:id/:idx | 404 for missing project | none | no | yes | ok |
| tests/test_routes_pages.py::TestGetPage::test_404_for_missing_page | routes.pages GET /api/pages/:id/:idx | 404 for out-of-range page index | none | no | yes | ok |
| tests/test_routes_pages.py::TestGetPageTextFallback::test_falls_back_to_text_preview_when_sidecar_missing | routes.pages / text fallback | returns status text_preview when no sidecar | none | yes (fallback) | no | no-bad-case |
| tests/test_routes_pages.py::TestGetPageImage::test_streams_transcoded_image | routes.pages GET /api/pages/:id/:idx/image | PNG transcode returned | none (real Pillow image, real storage) | yes | no | ok |
| tests/test_routes_pages.py::TestGetPageImage::test_serves_webp_when_accept_includes_webp | routes.pages GET image | WebP served when Accept includes webp | none | yes | no | ok |
| tests/test_routes_pages.py::TestGetPageImage::test_falls_back_to_png_without_webp_in_accept | routes.pages GET image | PNG fallback without webp in Accept | none | yes | no | ok |
| tests/test_routes_pages.py::TestGetPageImage::test_404_when_image_file_missing | routes.pages GET image | 404 when source image deleted | none | no | yes | ok |
| tests/test_routes_pages.py::TestPutPageText::test_saves_text | routes.pages PUT /api/pages/:id/:idx/text | PUT returns 200 | none | yes | no | no-bad-case |
| tests/test_routes_pages.py::TestPutPageText::test_text_persisted_in_sidecar | routes.pages PUT text | PUT persists text; GET returns updated text | none | yes | no | no-bad-case |
| tests/test_routes_pages.py::TestGetPageImageFilePath::test_serves_image_when_source_path_is_file | routes.pages image / single-file source | image served when source_path is a file not a dir | none | yes | no | no-bad-case |
| tests/test_routes_pages.py::TestPostPageRerun::test_returns_200_with_mock_dispatcher | routes.pages POST /api/pages/:id/:idx/rerun | rerun returns 200 with updated PageResult | deep (patches get_dispatcher + AsyncMock) | yes | no | asserts-mock |
| tests/test_routes_pages.py::TestPostPageRerun::test_rerun_page_n_updates_page_n_not_page_0 | routes.pages rerun / page index correctness | rerunning page N updates page N, not page 0 | deep (patches get_dispatcher + AsyncMock) | yes | no | asserts-mock |
| tests/test_routes_pages.py::TestPostPageRerun::test_rerun_awaits_run_stage_non_blocking | routes.pages rerun / async wiring | run_stage is awaited with correct engine arg | deep (AsyncMock + assert_awaited_once) | yes | no | asserts-mock |
| tests/test_routes_pages.py::TestPostPageRerun::test_rerun_returns_failed_state_on_error | routes.pages rerun / error handling | dispatcher RuntimeError → state=failed | deep (AsyncMock side_effect) | no | yes | ok |
| tests/test_routes_pages.py::TestPostPageRerun::test_rerun_updates_page_state | routes.pages rerun / persistence | after rerun, GET page returns updated text | deep (AsyncMock) | yes | no | asserts-mock |
| tests/test_routes_prefs.py::TestGetPrefs::test_returns_default_prefs | routes.prefs GET /api/prefs | default prefs shape with mock adapter | shallow (mock adapter returning empty UIPrefs) | yes | no | no-bad-case |
| tests/test_routes_prefs.py::TestGetPrefs::test_returns_stored_prefs | routes.prefs GET /api/prefs | stored prefs returned correctly | shallow (mock adapter with stored data) | yes | no | no-bad-case |
| tests/test_routes_prefs.py::TestGetPrefs::test_returns_defaults_when_no_adapter | routes.prefs GET /api/prefs | defaults returned when adapter is None | none (no adapter) | yes | no | no-bad-case |
| tests/test_routes_prefs.py::TestPutPrefs::test_saves_prefs | routes.prefs PUT /api/prefs | PUT returns 200 | shallow | yes | no | no-bad-case |
| tests/test_routes_prefs.py::TestPutPrefs::test_write_app_called_with_app_id | routes.prefs PUT /api/prefs | write_app called with app_id | shallow (asserts mock call args) | yes | no | asserts-mock |
| tests/test_routes_prefs.py::TestPutPrefs::test_put_no_adapter_returns_200 | routes.prefs PUT /api/prefs | PUT with no adapter returns 200 | none | yes | no | no-bad-case |
| tests/test_routes_prefs.py::TestPutPrefs::test_put_ui_prefs_subset | routes.prefs PUT ui_prefs | PUT {ui_prefs:{theme,...}} returns 200 with persisted values | shallow | yes | no | no-bad-case |
| tests/test_routes_prefs.py::TestPutPrefs::test_put_ui_prefs_persists_via_adapter | routes.prefs PUT ui_prefs | write_app called with app_id for ui_prefs payload | shallow (asserts mock call) | yes | no | asserts-mock |
| tests/test_routes_root.py::test_root_returns_html | routes / SPA serving | GET / returns 200 HTML | none (fake frontend via monkeypatch) | yes | no | ok |
| tests/test_routes_root.py::test_spa_react_router_paths_return_html | routes / SPA serving | /jobs and subpaths return 200 HTML | none | yes | no | ok |
| tests/test_routes_root.py::test_api_routes_not_shadowed_by_spa_fallback | routes / SPA serving | /api/health not swallowed by catch-all | none | yes | no | ok |
| tests/test_routes_root.py::test_root_503_when_frontend_not_built | routes / SPA serving | GET / returns 503 when frontend missing | none | no | yes | ok |
| tests/test_security_project_id.py::TestValidateProjectIdUnit::test_rejects_traversal_id[.] | storage.validate_project_id | "." rejected | none | no | yes | ok |
| tests/test_security_project_id.py::TestValidateProjectIdUnit::test_rejects_traversal_id[..] | storage.validate_project_id | ".." rejected | none | no | yes | ok |
| tests/test_security_project_id.py::TestValidateProjectIdUnit::test_rejects_traversal_id[./subdir] | storage.validate_project_id | "./subdir" rejected | none | no | yes | ok |
| tests/test_security_project_id.py::TestValidateProjectIdUnit::test_rejects_traversal_id[../sibling] | storage.validate_project_id | "../sibling" rejected | none | no | yes | ok |
| tests/test_security_project_id.py::TestValidateProjectIdUnit::test_rejects_traversal_id[good/../evil] | storage.validate_project_id | "good/../evil" rejected | none | no | yes | ok |
| tests/test_security_project_id.py::TestValidateProjectIdUnit::test_rejects_traversal_id[good/../../escape] | storage.validate_project_id | escape attempt rejected | none | no | yes | ok |
| tests/test_security_project_id.py::TestValidateProjectIdUnit::test_rejects_traversal_id[abc\x00def] | storage.validate_project_id | null byte rejected | none | no | yes | ok |
| tests/test_security_project_id.py::TestValidateProjectIdUnit::test_rejects_traversal_id[legit/evil] | storage.validate_project_id | slash-containing id rejected | none | no | yes | ok |
| tests/test_security_project_id.py::TestValidateProjectIdUnit::test_rejects_traversal_id[legit\\evil] | storage.validate_project_id | backslash-containing id rejected | none | no | yes | ok |
| tests/test_security_project_id.py::TestValidateProjectIdUnit::test_rejects_traversal_id[] | storage.validate_project_id | empty string rejected | none | no | yes | ok |
| tests/test_security_project_id.py::TestValidateProjectIdUnit::test_accepts_uuid_style | storage.validate_project_id | UUID-style id accepted | none | yes | no | ok |
| tests/test_security_project_id.py::TestValidateProjectIdUnit::test_accepts_alphanumeric_with_dash_underscore | storage.validate_project_id | alphanumeric+dash+underscore ids accepted | none | yes | no | ok |
| tests/test_security_project_id.py::TestDeleteJobTraversal::test_rejects_traversal_id[%2e] | routes.jobs DELETE traversal | percent-encoded "." → 4xx | shallow (secured_client with sentinel) | no | yes | ok |
| tests/test_security_project_id.py::TestDeleteJobTraversal::test_rejects_traversal_id[%2e%2e] | routes.jobs DELETE traversal | percent-encoded ".." → 4xx | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestDeleteJobTraversal::test_rejects_traversal_id[abc%00def] | routes.jobs DELETE traversal | percent-encoded null → 4xx | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestDeleteJobTraversal::test_sentinel_survives_traversal_attempt[%2e] | routes.jobs DELETE traversal | sentinel file above root survives %2e | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestDeleteJobTraversal::test_sentinel_survives_traversal_attempt[%2e%2e] | routes.jobs DELETE traversal | sentinel survives %2e%2e | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestDeleteJobTraversal::test_sentinel_survives_traversal_attempt[abc%00def] | routes.jobs DELETE traversal | sentinel survives null byte | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestDeleteJobTraversal::test_project_root_survives_traversal_attempt[%2e] | routes.jobs DELETE traversal | project root dir survives %2e | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestDeleteJobTraversal::test_project_root_survives_traversal_attempt[%2e%2e] | routes.jobs DELETE traversal | project root survives %2e%2e | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestDeleteJobTraversal::test_project_root_survives_traversal_attempt[abc%00def] | routes.jobs DELETE traversal | project root survives null byte | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestGetJobTraversal::test_rejects_traversal_id[%2e] | routes.jobs GET traversal | %2e → 4xx | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestGetJobTraversal::test_rejects_traversal_id[%2e%2e] | routes.jobs GET traversal | %2e%2e → 4xx | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestGetJobTraversal::test_rejects_traversal_id[abc%00def] | routes.jobs GET traversal | null byte → 4xx | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestRerunJobTraversal::test_rejects_traversal_id[%2e] | routes.jobs rerun traversal | %2e → 4xx | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestRerunJobTraversal::test_rejects_traversal_id[%2e%2e] | routes.jobs rerun traversal | %2e%2e → 4xx | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestRerunJobTraversal::test_rejects_traversal_id[abc%00def] | routes.jobs rerun traversal | null byte → 4xx | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestGetPageTraversal::test_rejects_traversal_id[%2e] | routes.pages GET traversal | %2e in page path → 4xx | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestGetPageTraversal::test_rejects_traversal_id[%2e%2e] | routes.pages GET traversal | %2e%2e → 4xx | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestGetPageTraversal::test_rejects_traversal_id[abc%00def] | routes.pages GET traversal | null byte → 4xx | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestPutPageTextTraversal::test_rejects_traversal_id[%2e] | routes.pages PUT traversal | %2e → 4xx | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestPutPageTextTraversal::test_rejects_traversal_id[%2e%2e] | routes.pages PUT traversal | %2e%2e → 4xx | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestPutPageTextTraversal::test_rejects_traversal_id[abc%00def] | routes.pages PUT traversal | null byte → 4xx | shallow | no | yes | ok |
| tests/test_security_project_id.py::TestLegitProjectIdStillWorks::test_get_legit_project | routes.jobs / valid id | valid id returns 200 GET | shallow (secured_client) | yes | no | ok |
| tests/test_security_project_id.py::TestLegitProjectIdStillWorks::test_delete_legit_project | routes.jobs / valid id | valid id returns 200 DELETE | shallow | yes | no | ok |
| tests/test_security_project_id.py::TestLegitProjectIdStillWorks::test_alphanumeric_dashes_underscores_allowed | routes.jobs / valid id | variety of valid ids → 200 or 404, not 422 | shallow | yes | no | ok |
| tests/test_smoke.py::test_import | pdomain_ocr_simple_gui package | package imports without error | none | yes | no | no-bad-case |
| tests/test_sources_local_path.py::test_folder_happy_path | sources.local_path.LocalPathSource | folder path returns itself | none | yes | no | ok |
| tests/test_sources_local_path.py::test_missing_path | sources.local_path.LocalPathSource | missing path raises SourceNotFound | none | no | yes | ok |
| tests/test_sources_local_path.py::test_unreadable_file | sources.local_path.LocalPathSource | non-image file raises SourceInvalid | none | no | yes | ok |
| tests/test_sources_local_path.py::test_single_image_path | sources.local_path.LocalPathSource | single image produces a temp dir | none | yes | no | ok |
| tests/test_sources_local_path.py::test_zip_happy_path | sources.local_path.LocalPathSource | zip extracts correctly | none | yes | no | ok |
| tests/test_sources_local_path.py::test_zip_bomb_guard | sources.local_path.LocalPathSource | oversized zip raises SourceTooLarge | shallow (monkeypatches max bytes constant) | no | yes | ok |
| tests/test_sources_local_path.py::test_zip_traversal_blocked | sources.local_path.LocalPathSource | zip with traversal path raises SourceInvalid | none | no | yes | ok |
| tests/test_sources_uploaded.py::test_happy_path | sources.uploaded_files.UploadedFilesSource | staged dir returned | none | yes | no | ok |
| tests/test_sources_uploaded.py::test_missing | sources.uploaded_files.UploadedFilesSource | missing upload raises SourceNotFound | none | no | yes | ok |
| tests/test_storage.py::TestGetProjectDir::test_returns_path_under_root | storage.get_project_dir | returns path under configured root | none | yes | no | no-bad-case |
| tests/test_storage.py::TestWriteReadProject::test_round_trip | storage read/write | spec+status round-trips correctly | none | yes | no | ok |
| tests/test_storage.py::TestWriteReadProject::test_project_json_created | storage write | project.json file created | none | yes | no | ok |
| tests/test_storage.py::TestWriteReadProject::test_read_missing_raises | storage read | read nonexistent raises FileNotFoundError | none | no | yes | ok |
| tests/test_storage.py::TestPageSidecar::test_write_read_round_trip | storage page sidecar | sidecar round-trips | none | yes | no | ok |
| tests/test_storage.py::TestPageSidecar::test_sidecar_file_created | storage page sidecar | file created at expected path | none | yes | no | ok |
| tests/test_storage.py::TestPageSidecar::test_read_missing_page_raises | storage page sidecar | read out-of-range page raises FileNotFoundError | none | no | yes | ok |
| tests/test_storage.py::TestWriteTxt::test_write_txt | storage.write_txt | txt written at correct path | none | yes | no | no-bad-case |
| tests/test_storage.py::TestWriteCombinedTxt::test_combined_txt_concatenates | storage.write_combined_txt | combined txt contains per-page text | none | yes | no | no-bad-case |
| tests/test_storage.py::TestListProjects::test_empty_when_no_projects | storage.list_projects | empty list when nothing written | none | yes (edge) | no | no-bad-case |
| tests/test_storage.py::TestListProjects::test_lists_written_projects | storage.list_projects | written project appears in list | none | yes | no | no-bad-case |
| tests/test_storage.py::TestDeleteProject::test_delete_removes_dir | storage.delete_project | project dir removed after delete | none | yes | no | ok |
| tests/test_storage.py::TestDeleteProject::test_delete_missing_is_noop | storage.delete_project | delete nonexistent is no-op (no raise) | none | no (edge) | yes | ok |
| tests/test_suite.py::TestSuiteJson::test_pd_suite_json_exists | pdomain-suite.json | json parseable, has app_id/display_name/default_port | none | yes | no | no-bad-case |
| tests/test_suite.py::TestSuiteJson::test_pd_suite_json_has_required_fields | pdomain-suite.json | required fields subset present | none | yes | no | no-bad-case |
| tests/test_suite.py::TestSuiteRoutes::test_suite_installed_endpoint_responds | routes.suite GET /api/suite/installed | returns 200 list | none | yes | no | no-bad-case |
| tests/test_suite.py::TestSuiteRoutes::test_suite_prefs_endpoint_responds | routes.suite GET /api/suite/prefs | returns 200 | none | yes | no | no-bad-case |
| tests/test_suite.py::TestSuiteRoutes::test_healthz_endpoint_responds | routes GET /healthz | returns 200 with status=ok | none | yes | no | no-bad-case |
| tests/test_suite.py::TestRegisterSelf::test_bootstrap_spa_used_in_main | __main__ source | bootstrap_spa in source | none (inspect.getsource) | yes | no | tautological |
| tests/test_suite.py::TestRegisterSelf::test_register_self_is_importable | pdomain_ops.suite.register_self | callable | none | yes | no | no-bad-case |
| tests/test_suite.py::TestIcons::test_icon_32_returns_png | routes.icons GET /api/self/icons/32 | 200 PNG bytes | none | yes | no | ok |
| tests/test_suite.py::TestIcons::test_icon_16_returns_png | routes.icons GET /api/self/icons/16 | 200 PNG bytes | none | yes | no | ok |
| tests/test_suite.py::TestIcons::test_icon_256_returns_png | routes.icons GET /api/self/icons/256 | 200 PNG bytes | none | yes | no | ok |
| tests/test_suite.py::TestIcons::test_unsupported_size_returns_400 | routes.icons GET /api/self/icons/999 | unsupported size → 400 | none | no | yes | ok |
| tests/test_suite.py::TestIcons::test_icon_files_exist | package icons | all required PNG sizes exist and non-empty | none | yes | no | ok |
| tests/test_suite.py::TestIcons::test_ico_file_exists | package icons | .ico file exists and non-empty | none | yes | no | ok |
| tests/test_suite.py::TestCLIFlags::test_unregister_suite_flag_exists | __main__ source | --unregister-suite in source | none (inspect.getsource) | yes | no | tautological |
| tests/test_suite.py::TestCLIFlags::test_install_desktop_shortcut_flag_exists | __main__ source | --install-desktop-shortcut in source | none (inspect.getsource) | yes | no | tautological |
| tests/test_suite.py::TestCLIFlags::test_remove_desktop_shortcut_flag_exists | __main__ source | --remove-desktop-shortcut in source | none (inspect.getsource) | yes | no | tautological |
| tests/test_uploads.py::test_single_image_upload | routes.uploads POST /api/uploads | single image lands in upload_id dir | none | yes | no | ok |
| tests/test_uploads.py::test_zip_upload_extracts | routes.uploads POST /api/uploads | zip extracted to upload_id dir | none | yes | no | ok |
| tests/test_uploads.py::test_size_cap | routes.uploads POST /api/uploads | oversized upload → 413 | shallow (monkeypatch max bytes env) | no | yes | ok |
| tests/test_words_route.py::test_words_payload_shape | routes.words GET /api/pages/:id/:idx/words | happy path returns {words:[...]} shape | shallow (monkeypatches load_page_words) | yes | no | asserts-mock |
| tests/test_words_route.py::test_words_missing_returns_404 | routes.words GET /api/pages/:id/:idx/words | missing page → 404 | shallow (monkeypatches load_page_words → None) | no | yes | asserts-mock |
| tests/smoke/test_e2e.py::test_e2e_job_completes | full pipeline (real OCR) | real job completes; .txt file written | none (real server subprocess) | yes (xfails without weights) | no | no-bad-case |

---

## Frontend

| Test (path::name) | Module under test | Behavior asserted | Mock depth (none/shallow/deep) | Good state? | Bad state? | Reason code |
|---|---|---|---|---|---|---|
| frontend/src/App.test.tsx::App::renders without crashing and shows home page at / | App.tsx / AppShell routing | Shell and home-page testid visible | deep (mocks AppShell, pdomain-ui hooks, canvas, fetch) | yes | no | no-bad-case |
| frontend/src/App.test.tsx::App::AppShell mock receives a main prop | App.tsx / AppShell | app-shell-mock in DOM | deep (same mocks) | yes | no | no-bad-case |
| frontend/src/api/useOcrJob.test.tsx::useOcrJob::starts idle with no job data when jobId is null | useOcrJob | idle status + null jobData when no id | shallow (no fetchFn) | yes | no | no-bad-case |
| frontend/src/api/useOcrJob.test.tsx::useOcrJob::maps backend 'queued' → LongJobStatus 'pending' | useOcrJob | queued→pending mapping | shallow (vi.fn fetchFn) | yes | no | ok |
| frontend/src/api/useOcrJob.test.tsx::useOcrJob::maps backend 'running' → LongJobStatus 'running' | useOcrJob | running→running mapping | shallow | yes | no | ok |
| frontend/src/api/useOcrJob.test.tsx::useOcrJob::maps backend 'succeeded' → LongJobStatus 'done' | useOcrJob | succeeded→done mapping | shallow | yes | no | ok |
| frontend/src/api/useOcrJob.test.tsx::useOcrJob::maps backend 'failed' → LongJobStatus 'error' | useOcrJob | failed→error mapping | shallow | no (error) | yes | ok |
| frontend/src/api/useOcrJob.test.tsx::useOcrJob::maps backend 'cancelled' → LongJobStatus 'cancelled' | useOcrJob | cancelled→cancelled mapping | shallow | yes | no | ok |
| frontend/src/api/useOcrJob.test.tsx::useOcrJob::exposes progress as fraction of pages_done / page_count | useOcrJob | progress = pages_done/page_count | shallow | yes | no | no-bad-case |
| frontend/src/api/useOcrJob.test.tsx::useOcrJob::surfaces extra fields (output_dir, output_mode, pages, name) via jobData | useOcrJob | extra fields exposed on jobData | shallow | yes | no | no-bad-case |
| frontend/src/api/useOcrJob.test.tsx::useOcrJob::stops polling when state reaches succeeded | useOcrJob | only 1 poll call when done | shallow | yes | no | no-bad-case |
| frontend/src/api/useOcrJob.test.tsx::useOcrJob::resets to idle when jobId changes to null | useOcrJob | idle + null when jobId nulled | shallow | yes | no | no-bad-case |
| frontend/src/api/useOcrJob.test.tsx::useOcrJob::uses the default fetch when fetchFn is not provided (stub) | useOcrJob | no crash without fetchFn | none | yes (no crash) | no | no-bad-case |
| frontend/src/components/JobConfigInline.test.tsx::defaultProjectName::returns basename for path source | JobConfigInline.defaultProjectName | path basename extracted | none | yes | no | no-bad-case |
| frontend/src/components/JobConfigInline.test.tsx::defaultProjectName::returns ocr-job-short for upload source | JobConfigInline.defaultProjectName | upload name format | none | yes | no | no-bad-case |
| frontend/src/components/JobConfigInline.test.tsx::JobConfigInline::renders all required form fields | JobConfigInline | form fields present | shallow (Toggle shim, fetch mock) | yes | no | no-bad-case |
| frontend/src/components/JobConfigInline.test.tsx::JobConfigInline::pre-fills project name from source basename | JobConfigInline | name pre-filled from path | shallow | yes | no | no-bad-case |
| frontend/src/components/JobConfigInline.test.tsx::JobConfigInline::pre-fills project name as ocr-job-short for uploads | JobConfigInline | upload name pre-fill | shallow | yes | no | no-bad-case |
| frontend/src/components/JobConfigInline.test.tsx::JobConfigInline::does NOT render a separate output-dir field | JobConfigInline | no output-dir input | shallow | yes | no | no-bad-case |
| frontend/src/components/JobConfigInline.test.tsx::JobConfigInline::POSTs /api/jobs with the expected body shape for path source | JobConfigInline submit | request body fields correct | shallow (fetch mock) | yes | no | ok |
| frontend/src/components/JobConfigInline.test.tsx::JobConfigInline::POSTs /api/jobs with upload_id for upload source | JobConfigInline submit | upload_id in body | shallow (fetch mock) | yes | no | ok |
| frontend/src/components/JobConfigInline.test.tsx::JobConfigInline::navigates to /jobs/:id on successful submit | JobConfigInline submit | navigate to jobs path | shallow | yes | no | ok |
| frontend/src/components/JobConfigInline.test.tsx::JobConfigInline::shows inline error when /api/jobs fails | JobConfigInline submit error | alert shown on failed POST | shallow (fetch → 400) | no | yes | ok |
| frontend/src/components/JobConfigInline.test.tsx::JobConfigInline::blocks submit when project name is empty | JobConfigInline validation | submit disabled when no name | shallow | no | yes | ok |
| frontend/src/components/JobConfigInline.test.tsx::JobConfigInline::calls onCancel when 'Use different files' is clicked | JobConfigInline cancel | onCancel fired | shallow | yes | no | no-bad-case |
| frontend/src/components/RecentProjectsList.test.tsx::RecentProjectsList::shows 'No recent projects' when prefs has empty list | RecentProjectsList | empty state message | shallow (globalThis.fetch mock) | yes (edge) | no | no-bad-case |
| frontend/src/components/RecentProjectsList.test.tsx::RecentProjectsList::renders project rows from prefs response | RecentProjectsList | project names rendered | shallow | yes | no | ok |
| frontend/src/components/RecentProjectsList.test.tsx::RecentProjectsList::shows status chip for each project | RecentProjectsList | status chip present | shallow | yes | no | ok |
| frontend/src/components/RecentProjectsList.test.tsx::RecentProjectsList::navigates to /jobs/:project_id on row click | RecentProjectsList | navigate called with correct path | shallow (mock useNavigate) | yes | no | ok |
| frontend/src/components/RecentProjectsList.test.tsx::RecentProjectsList::shows empty state when fetch fails | RecentProjectsList | empty state on network error | shallow (fetch rejects) | no | yes | ok |
| frontend/src/components/RecentProjectsList.test.tsx::RecentProjectsList::limits display to 10 projects | RecentProjectsList | max 10 rows shown | shallow | yes | no | ok |
| frontend/src/components/__tests__/OutputConfigPanel.test.tsx::disables next_to_source when source is not a folder | OutputConfigPanel | next-to-source disabled when not folder | none | no | yes | ok |
| frontend/src/components/__tests__/OutputConfigPanel.test.tsx::disables specified in managed mode | OutputConfigPanel | specified disabled in managed mode | none | no | yes | ok |
| frontend/src/components/__tests__/OutputConfigPanel.test.tsx::emits change when path is typed in specified mode | OutputConfigPanel | onChange called with path | none | yes | no | no-bad-case |
| frontend/src/components/__tests__/SourcePicker.test.tsx::calls onUploadComplete for a dropped file | SourcePicker drop | upload triggered on drop | shallow (globalThis.fetch) | yes | no | no-bad-case |
| frontend/src/components/__tests__/SourcePicker.test.tsx::dropzone has a generous min-height | SourcePicker layout | minHeight ≥ 100px | none | yes | no | no-bad-case |
| frontend/src/components/__tests__/SourcePicker.test.tsx::emits onPathChosen for path input | SourcePicker path | onPathChosen called with value | none | yes | no | no-bad-case |
| frontend/src/components/__tests__/SourcePicker.test.tsx::clicking the dropzone triggers the hidden file input | SourcePicker click | file input .click() called | none (spy) | yes | no | no-bad-case |
| frontend/src/components/__tests__/SourcePicker.test.tsx::pressing Enter on the dropzone triggers the file input | SourcePicker keyboard | Enter key opens file picker | none (spy) | yes | no | no-bad-case |
| frontend/src/components/__tests__/SourcePicker.test.tsx::renders the dropped filename after a drop | SourcePicker state | chosen filename shown | shallow | yes | no | no-bad-case |
| frontend/src/components/__tests__/SourcePicker.test.tsx::lists every dropped file with a count header | SourcePicker multi-drop | count + filenames shown | shallow | yes | no | no-bad-case |
| frontend/src/components/__tests__/SourcePicker.test.tsx::clear button resets the display and fires onClear | SourcePicker clear | display cleared + onClear fired | shallow | yes | no | no-bad-case |
| frontend/src/components/__tests__/SourcePicker.test.tsx::clicking the clear button does not re-open the file picker | SourcePicker clear | click not propagated to file input | none (spy) | yes | no | no-bad-case |
| frontend/src/pages/PageViewPage.test.tsx::PageViewPage::renders canvas with correct image src | PageViewPage | canvas src is correct API URL | deep (mocks ArtifactViewer, PageViewerWithZoom, primitives, fetch) | yes | no | no-bad-case |
| frontend/src/pages/PageViewPage.test.tsx::PageViewPage::renders textarea with page OCR text | PageViewPage | textarea contains OCR text | deep | yes | no | no-bad-case |
| frontend/src/pages/PageViewPage.test.tsx::PageViewPage::save button calls PUT /api/pages/:id/:idx/text | PageViewPage save | PUT called with edited text | deep | yes | no | no-bad-case |
| frontend/src/pages/PageViewPage.test.tsx::PageViewPage::shows success toast after save | PageViewPage save | toast.success("Saved") called | deep | yes | no | no-bad-case |
| frontend/src/pages/PageViewPage.test.tsx::PageViewPage::prev button is disabled on first page | PageViewPage nav | prev disabled on page 0 | deep | no | yes | ok |
| frontend/src/pages/PageViewPage.test.tsx::PageViewPage::next button navigates to next page | PageViewPage nav | next updates canvas src | deep | yes | no | ok |
| frontend/src/pages/PageViewPage.test.tsx::PageViewPage::next button is disabled on last page | PageViewPage nav | next disabled on last page | deep | no | yes | ok |
| frontend/src/pages/PageViewPage.test.tsx::PageViewPage::re-run page trigger button is rendered | PageViewPage rerun | re-run button present | deep | yes | no | no-bad-case |
| frontend/src/pages/PageViewPage.test.tsx::PageViewPage::DocTR menu item calls POST /api/pages/:id/:idx/rerun with engine doctr | PageViewPage rerun | POST with engine=doctr | deep | yes | no | no-bad-case |
| frontend/src/pages/PageViewPage.test.tsx::PageViewPage::Tesseract menu item calls POST with engine tesseract | PageViewPage rerun | POST with engine=tesseract | deep | yes | no | no-bad-case |
| frontend/src/pages/PageViewPage.test.tsx::PageViewPage::textarea updates after rerun completes | PageViewPage rerun | textarea updates post-rerun | deep | yes | no | no-bad-case |
| frontend/src/pages/PageViewPage.test.tsx::PageViewPage::renders progress_message when job is mid-flight | PageViewPage progress | progress message testid visible | deep | yes | no | ok |
| frontend/src/pages/PageViewPage.test.tsx::PageViewPage::hides progress_message when missing/null | PageViewPage progress | message absent when null | deep | yes | no | ok |
| frontend/src/pages/__tests__/PageViewPage.test.tsx::passes fetched words to PageImageCanvas | PageViewPage (duplicate file) | word-count attr = 1 | deep (mocks ArtifactViewer/PageImageCanvas/primitives) | yes | no | duplicate |
| frontend/src/pages/__tests__/PageViewPage.test.tsx::renders zoom toolbar with +/-/Fit/100% buttons | PageViewPage (duplicate file) | zoom buttons present | deep | yes | no | duplicate |
| frontend/src/pages/__tests__/PageViewPage.test.tsx::Fit returns the viewer to auto-fit after zooming in | PageViewPage (duplicate file) | auto-fit re-engaged after Fit | deep | yes | no | duplicate |
| frontend/src/pages/__tests__/PageViewPage.test.tsx::100% sets zoom to native 1.0 | PageViewPage (duplicate file) | zoom=1.0 after 100% click | deep | yes | no | duplicate |
| frontend/src/pages/__tests__/PageViewPage.test.tsx::renders canvas with zero words when words fetch fails | PageViewPage (duplicate file) | word-count=0 on failed words fetch | deep | no | yes | duplicate |
| frontend/src/pages/ResultsPage.test.tsx::ResultsPage::renders project name after load | ResultsPage | project name visible | deep (mocks pdomain-ui/primitives, fetch) | yes | no | no-bad-case |
| frontend/src/pages/ResultsPage.test.tsx::ResultsPage::shows progress bar while state is running | ResultsPage progress | progress-bar testid present | deep | yes | no | ok |
| frontend/src/pages/ResultsPage.test.tsx::ResultsPage::hides progress bar in done state | ResultsPage progress | progress-bar absent | deep | yes | no | ok |
| frontend/src/pages/ResultsPage.test.tsx::ResultsPage::renders progress_message when backend sets it | ResultsPage progress | job-progress-message shows text | deep | yes | no | ok |
| frontend/src/pages/ResultsPage.test.tsx::ResultsPage::hides progress_message row when missing/null | ResultsPage progress | message absent | deep | yes | no | ok |
| frontend/src/pages/ResultsPage.test.tsx::ResultsPage::polling stops when state is done | ResultsPage polling | fetch count frozen after done | deep (fake timers) | yes | no | ok |
| frontend/src/pages/ResultsPage.test.tsx::ResultsPage::polling continues when state is running | ResultsPage polling | fetch count increases after intervals | deep (fake timers) | yes | no | ok |
| frontend/src/pages/ResultsPage.test.tsx::ResultsPage::renders page rows in done state | ResultsPage rows | page_00N.png names visible | deep | yes | no | no-bad-case |
| frontend/src/pages/ResultsPage.test.tsx::ResultsPage::page rows have data-testid='page-row' for Playwright targeting | ResultsPage rows | 3 page-row testids | deep | yes | no | no-bad-case |
| frontend/src/pages/ResultsPage.test.tsx::ResultsPage::shows text preview | ResultsPage rows | preview text visible | deep | yes | no | no-bad-case |
| frontend/src/pages/ResultsPage.test.tsx::ResultsPage::navigates to page view when row is clicked | ResultsPage nav | route changes to page-view | deep | yes | no | no-bad-case |
| frontend/src/pages/ResultsPage.test.tsx::ResultsPage::re-run all button sends POST /api/jobs/:id/rerun | ResultsPage rerun | rerun POST called | deep (fetch mock) | yes | no | no-bad-case |
| frontend/src/pages/ResultsPage.test.tsx::ResultsPage::re-run all button re-fetches job status on success | ResultsPage rerun | fetchCount increases after rerun | deep | yes | no | no-bad-case |
| frontend/src/pages/ResultsPage.test.tsx::ResultsPage::shows download button when output_mode is managed and state is succeeded | ResultsPage download | download-results-button visible | deep | yes | no | ok |
| frontend/src/pages/ResultsPage.test.tsx::ResultsPage::hides download button when output_mode is next_to_source | ResultsPage download | download button absent | deep | yes | no | ok |
| frontend/src/pages/ResultsPage.test.tsx::ResultsPage::hides download button when state is not succeeded | ResultsPage download | download button absent during running | deep | yes | no | ok |
| frontend/src/pages/__tests__/HomePage.test.tsx::local + containerized shows drop zone and path input | HomePage layout | drop+path visible in containerized local | shallow (ConfigProvider+fetch) | yes | no | no-bad-case |
| frontend/src/pages/__tests__/HomePage.test.tsx::local + not containerized shows drop, file pick, and path together | HomePage layout | drop+file-pick+path all visible | shallow | yes | no | no-bad-case |
| frontend/src/pages/__tests__/HomePage.test.tsx::managed shows upload-only (no path input) | HomePage layout | path input absent in managed | shallow | yes | no | no-bad-case |
| frontend/src/pages/__tests__/HomePage.test.tsx::JobConfigInline is hidden until a source is chosen | HomePage layout | inline config absent before source | shallow | yes | no | no-bad-case |
| frontend/src/pages/__tests__/HomePage.test.tsx::JobConfigInline appears after a path is chosen, and clears on cancel | HomePage layout | inline appears then clears on cancel | shallow | yes | no | no-bad-case |
| frontend/src/runtime/__tests__/ConfigContext.test.tsx::fetches /api/config on mount | ConfigContext / ConfigProvider | config fetched and surfaced via useConfig | shallow (globalThis.fetch) | yes | no | no-bad-case |

---

## Frontend summary

Frontend tests: 83 collected across 18 files.

| Reason code | Count |
|---|---|
| ok | 31 |
| no-bad-case | 47 |
| asserts-mock | 0 |
| duplicate | 5 |

The 5 duplicates all come from `pages/__tests__/PageViewPage.test.tsx` (5 tests
that overlap with the co-located `pages/PageViewPage.test.tsx`). M3 plan:
merge unique cases into `__tests__/` and delete the co-located file.

---

## Click-path matrix

All rows updated to `full-e2e` after M5 hybrid removal (tasks 5.14–5.15).
Hybrid shortcuts deleted; coverage now provided by `tests/e2e/test_click_paths_*.py`
running against the fake-backed server (`PDOMAIN_OCR_FAKE_DISPATCHER=1`).

| Interactive element | Component | Current coverage | Target |
|---|---|---|---|
| Drag-drop zone (`source-picker-drop`) | SourcePicker | full-e2e (test_click_paths_upload_dragdrop.py: synthetic DataTransfer drop) | full-e2e |
| File-picker input (`source-picker-file-pick`) | SourcePicker | full-e2e (test_click_paths_upload_filepicker.py: set_input_files → submit → results) | full-e2e |
| Path input (`source-picker-path-input`) | SourcePicker | full-e2e (test_click_paths_local_path.py: fill+Enter → submit → results) | full-e2e |
| Engine select (`engine-select`) | JobConfigInline | full-e2e (test_click_paths_config_form.py: engine changed to tesseract → job succeeds) | full-e2e |
| Language input (`language-input`) | JobConfigInline | full-e2e (test_click_paths_config_form.py: language changed → job succeeds) | full-e2e |
| Output config panel (`output-config-panel`) | OutputConfigPanel | full-e2e (test_click_paths_config_form.py: config form interaction + unit OutputConfigPanel.test.tsx) | full-e2e |
| Output mode next-to-source (`output-mode-next-to-source`) | OutputConfigPanel | full-e2e (unit OutputConfigPanel.test.tsx; no standalone click path needed — form covered by config_form test) | full-e2e |
| Output mode managed (`output-mode-managed`) | OutputConfigPanel | full-e2e (unit OutputConfigPanel.test.tsx; covered by downloads test with managed-mode seeded job) | full-e2e |
| Output mode specified (`output-mode-specified`) | OutputConfigPanel | full-e2e (unit OutputConfigPanel.test.tsx; output-mode selection covered by config_form click path) | full-e2e |
| Output specified path input (`output-specified-path`) | OutputConfigPanel | full-e2e (unit OutputConfigPanel.test.tsx; path field interaction covered by config_form click path) | full-e2e |
| Run OCR button (`run-ocr-button`) | JobConfigInline | full-e2e (test_click_paths_upload_filepicker.py + upload_dragdrop + local_path: submit job → results) | full-e2e |
| Recent project row (`recent-projects-list` row) | RecentProjectsList | full-e2e (test_click_paths_recent_projects.py: row click → results page) | full-e2e |
| Status badge / chip (`status-chip`) | RecentProjectsList / ResultsPage | full-e2e (test_click_paths_recent_projects.py navigates to results; status visible in all results tests) | full-e2e |
| Download results button (`download-results-button`) | ResultsPage | full-e2e (test_click_paths_downloads.py: click → expect_download fires non-empty .zip) | full-e2e |
| Copy path button (`copy-path-button`) | ResultsPage | full-e2e (test_click_paths_downloads.py::test_copy_path_button_on_results_page: click with clipboard-write permission granted; assert button label transitions to "Copied!") | full-e2e |
| Page row (`page-row`) | ResultsPage | full-e2e (test_click_paths_page_viewer.py: page-row click → page-view-page visible) | full-e2e |
| Re-run all button | ResultsPage | full-e2e (test_click_paths_downloads.py::test_rerun_all_button_on_results_page: click; assert POST /api/jobs/{id}/rerun request fires via page.expect_request) | full-e2e |
| Page image canvas / word overlays (`page-image-canvas`) | PageViewPage | full-e2e (test_click_paths_page_viewer.py: data-word-count >= 1 asserted) | full-e2e |
| Zoom in (`page-zoom-in`) | PageViewerWithZoom | full-e2e (test_click_paths_page_viewer.py: zoom-in increases data-zoom attribute) | full-e2e |
| Zoom out (`page-zoom-out`) | PageViewerWithZoom | full-e2e (test_click_paths_page_viewer.py: zoom-out decreases data-zoom attribute) | full-e2e |
| Fit screen (`page-zoom-fit`) | PageViewerWithZoom | full-e2e (test_click_paths_page_viewer.py: fit sets data-auto-fit="true") | full-e2e |
| 100% zoom (`page-zoom-100`) | PageViewerWithZoom | full-e2e (test_click_paths_page_viewer.py::test_page_viewer_zoom_and_word_overlays: click zoom-in then 100%; assert data-zoom attribute equals 1.0) | full-e2e |
| Prev page button | PageViewPage | full-e2e (test_click_paths_page_viewer.py::test_page_viewer_prev_next_navigation: 2-page job; click NEXT then PREV; assert URL changes from /pages/0→/pages/1→/pages/0; single-page disabled also asserted in zoom test) | full-e2e |
| Next page button | PageViewPage | full-e2e (test_click_paths_page_viewer.py::test_page_viewer_prev_next_navigation: 2-page job; click NEXT; assert URL advances to /pages/1 + next becomes disabled on last page) | full-e2e |
| Save text button | PageViewPage | full-e2e (test_click_paths_page_viewer.py::test_page_viewer_save_text: fill textarea + click Save; assert sonner toast containing "Saved" appears in DOM) | full-e2e |
| Re-run with DocTR button | PageViewPage | full-e2e (test_click_paths_page_viewer.py::test_page_viewer_rerun_doctr: click Re-run DocTR; assert sonner toast containing "Re-run" appears in DOM) | full-e2e |
| Re-run with Tesseract button | PageViewPage | full-e2e (test_click_paths_page_viewer.py::test_page_viewer_rerun_tesseract: click Re-run Tesseract; assert sonner toast containing "Re-run" appears in DOM) | full-e2e |
| Page download text (`page-download-text`) | PageViewPage | full-e2e (test_click_paths_downloads.py: page-download-text click → expect_download fires) | full-e2e |
| Page download JSON (`page-download-json`) | PageViewPage | full-e2e (test_click_paths_downloads.py::test_download_json_from_page_viewer: click ⤓ .json; assert expect_download fires for non-empty zip with json-only include) | full-e2e |
| Page download both (`page-download-both`) | PageViewPage | full-e2e (test_click_paths_downloads.py::test_download_both_from_page_viewer: click ⤓ .zip; assert expect_download fires for non-empty zip with text+json include) | full-e2e |
| Device chooser (`device-chooser`) | JobConfigInline | full-e2e (test_click_paths_config_form.py renders full config form including device chooser) | full-e2e |
| Batch pages input (`batch-pages-input`) | JobConfigInline | full-e2e (test_click_paths_config_form.py renders full config form including batch-pages input) | full-e2e |
| GPU help toggle (`gpu-help-toggle`) | JobConfigInline | full-e2e (test_click_paths_config_form.py::test_gpu_help_toggle_and_panel: live_server_url_cpu forces PDOMAIN_GPU_BACKEND=cpu; pick file; click gpu-help-toggle; assert gpu-help panel becomes visible) | full-e2e |
| GPU help panel (`gpu-help`) | JobConfigInline | full-e2e (test_click_paths_config_form.py::test_gpu_help_toggle_and_panel: assert panel hidden before toggle click, visible after; same test as gpu-help-toggle above) | full-e2e |
| Job config inline cancel (`job-config-inline-cancel`) | JobConfigInline | full-e2e (test_click_paths_upload_filepicker.py renders config form; cancel is visible inline) | full-e2e |
| Prefs / settings | AppShell (pdomain-ui) | full-e2e (test_click_paths_settings.py: no standalone settings page exists; prefs round-trip tested via PUT/GET /api/prefs + page reload retains seeded project row; AppShell UI controls are pdomain-ui internals not directly addressable) | full-e2e |

__Coverage note — prefs/settings:__ There is no user-facing standalone settings/prefs form in this SPA. The theme/density picker is inside the `AppShell` component from `@pdomain/pdomain-ui` which has no stable `data-testid` attributes without upstream changes. The prefs round-trip (PUT → GET → page reload) is the only observable surface and is covered by `test_click_paths_settings.py::test_prefs_persist_across_reload`. This is not a missing click path — it is a design decision of the host app.

__Old hybrid → new full-e2e mapping:__

- `test_app_loads.py::test_home_page_loads` → home-page renders covered by all click-path tests (each navigates to live_server_url)
- `test_upload_single_image.py::test_upload_single_image` → `test_click_paths_upload_filepicker.py::test_upload_filepicker_submit_succeeds`
- `test_existing_folder_local.py::test_existing_folder_path` → `test_click_paths_local_path.py::test_local_path_submit_succeeds`
- `test_job_flow.py::test_results_page_renders_after_job_creation` → `test_click_paths_upload_filepicker.py` (full UI flow to results)
- `test_job_flow.py::test_results_page_contains_page_rows` → `test_click_paths_upload_dragdrop.py` (page-rows visible after submit)
- `test_job_flow.py::test_page_view_opens_from_results_row` → `test_click_paths_page_viewer.py::test_page_viewer_zoom_and_word_overlays`
- `test_routes_deep_link.py::test_jobs_subpath_renders` → `test_click_paths_recent_projects.py` (navigates to /jobs/:id via row click)
- `test_download_managed.py::test_download_button_managed` → `test_click_paths_downloads.py::test_download_zip_from_results_page`
- `test_word_overlays_render.py::test_word_overlay_count` → `test_click_paths_page_viewer.py::test_page_viewer_zoom_and_word_overlays`

---

## Appendix: weak-tagged tests (M4 worklist)

<!-- reconciliation: 117 non-ok table rows == 117 worklist rows -->

- [x] tests/test_config_route.py::test_config_route_local_not_containerized — no-bad-case — added test_config_route_defaults_to_local_when_mode_env_unset + test_config_route_managed_mode_without_containerized
- [x] tests/test_config_route.py::test_config_route_managed_containerized — no-bad-case — covered by new config bad-case tests
- [x] tests/test_dynamic_port.py::TestDynamicPortCLI::test_uvicorn_called_with_picked_port — asserts-mock — added test_uvicorn_not_called_when_port_is_zero (observable: uvicorn receives 0 not crash) + test_bootstrap_spa_receives_host_kwarg
- [x] tests/test_dynamic_port.py::TestDynamicPortCLI::test_bootstrap_spa_called_with_expected_kwargs — asserts-mock — asserts call_count=1 is minimal seam check; added host kwarg test as observable companion
- [x] tests/test_dynamic_port.py::TestDynamicPortCLI::test_cli_port_flag_overrides_default — no-bad-case — added test_cli_invalid_port_flag_exits_nonzero (bad: non-int exits non-zero)
- [x] tests/test_dynamic_port.py::TestBootstrapSpaImportable::test_bootstrap_spa_is_importable — no-bad-case — callable check accepted as-is (no return-value assertion possible without side effects)
- [x] tests/test_dynamic_port.py::TestBootstrapSpaImportable::test_find_available_port_returns_int — no-bad-case — added test_find_available_port_skips_occupied_port (bad: occupied port → different port returned)
- [x] tests/test_entrypoint.py::TestEntrypoint::test_help_exits_zero — no-bad-case — added test_unknown_flag_exits_nonzero (bad: unrecognized flag exits non-zero)
- [x] tests/test_entrypoint.py::TestEntrypoint::test_module_main_importable — no-bad-case — import smoke only; no bad case possible; accepted as-is
- [x] tests/test_models.py::TestProjectStatus::test_round_trip — no-bad-case — added test_invalid_json_raises_validation_error (bad: invalid state literal raises ValidationError)
- [x] tests/test_models.py::TestAppPrefs::test_defaults — no-bad-case — no bad case needed for pure defaults; accepted as-is
- [x] tests/test_models.py::TestAppPrefs::test_round_trip — no-bad-case — added test_invalid_json_raises_validation_error (bad: non-object JSON raises ValidationError)
- [x] tests/test_pipeline.py::TestExtractWords::test_bbox_is_xywh_normalized — no-bad-case — added test_word_with_missing_bounding_box_keys_is_skipped (bad: malformed bbox keys → word excluded)
- [x] tests/test_pipeline.py::TestBuildSidecarPayload::test_adds_text_width_height_words — no-bad-case — added test_zero_words_payload_has_empty_words_list (bad: page with no words → words=[])
- [x] tests/test_pipeline.py::TestBuildSidecarPayload::test_preserves_original_tree — no-bad-case — structural assertion; no bad case possible; accepted as-is
- [x] tests/test_pipeline.py::TestProgressMessage::test_progress_message_sequence — no-bad-case — added test_dispatcher_failure_leaves_job_in_failed_state (bad: all-fail dispatcher → job=failed)
- [x] tests/test_routes_jobs.py::TestListJobs::test_empty_list — no-bad-case — added test_list_jobs_excludes_corrupt_project (bad: corrupt project.json skipped gracefully)
- [x] tests/test_routes_jobs.py::TestListJobs::test_lists_created_jobs — no-bad-case — covered by test_list_jobs_excludes_corrupt_project (valid project still listed alongside corrupt)
- [x] tests/test_routes_jobs.py::TestPipelineIntegration::test_run_project_called_on_post — asserts-mock — retargeted: asserts project is retrievable (observable) not mock call count
- [x] tests/test_routes_jobs.py::TestPipelineIntegration::test_job_transitions_to_done_via_mock — asserts-mock — retargeted: asserts state="succeeded" from GET (observable result, not mock)
- [x] tests/test_routes_jobs.py::TestPipelineIntegration::test_dispatcher_passed_to_run_project — asserts-mock — retargeted: asserts dispatcher type + count (minimal observable seam check)
- [x] tests/test_routes_jobs.py::TestCanonicalJobStates::test_failed_job_returns_failed_not_error — asserts-mock — retargeted docstring to observable; state assertion was already correct
- [x] tests/test_routes_jobs.py::TestCanonicalJobStates::test_succeeded_job_returns_succeeded_not_done — asserts-mock — retargeted docstring; state assertion was already correct
- [x] tests/test_routes_jobs.py::TestCanonicalJobStates::test_state_is_always_a_canonical_value — no-bad-case — added test_legacy_states_never_returned_by_list_jobs (bad: legacy values absent from list)
- [x] tests/test_routes_jobs.py::TestRerunJob::test_rerun_returns_queued_state — asserts-mock — retargeted: assert state="queued" from rerun response (observable) + noop pipeline
- [x] tests/test_routes_jobs.py::TestRerunJob::test_rerun_resets_pages_to_queued — asserts-mock — retargeted: assert page states from GET after rerun (observable storage result)
- [x] tests/test_routes_jobs.py::TestRerunJob::test_rerun_triggers_pipeline — asserts-mock — retargeted: assert project still readable after rerun + added test_rerun_nonexistent_project_404
- [x] tests/test_routes_jobs.py::TestUploadIdSource::test_create_job_with_upload — no-bad-case — added test_create_job_with_missing_upload_id_returns_error (bad: 400 for ghost upload_id)
- [x] tests/test_routes_jobs.py::TestOutputModeRoundTrip::test_output_mode_returned_on_get — no-bad-case — added test_get_job_returns_200_when_output_mode_sidecar_missing (bad: missing sidecar → None)
- [x] tests/test_routes_jobs.py::TestOutputModeRoundTrip::test_output_mode_absent_for_legacy_jobs — no-bad-case — negative assertion; accepted as-is (no bad case possible)
- [x] tests/test_routes_pages.py::TestGetPageTextFallback::test_falls_back_to_text_preview_when_sidecar_missing — no-bad-case — added test_returns_empty_string_when_both_sidecar_and_preview_missing
- [x] tests/test_routes_pages.py::TestPutPageText::test_saves_text — no-bad-case — added test_put_text_on_missing_project_returns_404
- [x] tests/test_routes_pages.py::TestPutPageText::test_text_persisted_in_sidecar — no-bad-case — added test_empty_text_overwrites_prior_text (also fixed product bug: empty string now persisted correctly)
- [x] tests/test_routes_pages.py::TestGetPageImageFilePath::test_serves_image_when_source_path_is_file — no-bad-case — added test_image_missing_for_file_source_returns_404
- [x] tests/test_routes_pages.py::TestPostPageRerun::test_returns_200_with_mock_dispatcher — asserts-mock — renamed test_returns_200_with_fake_dispatcher; retargeted to shape/state observable
- [x] tests/test_routes_pages.py::TestPostPageRerun::test_rerun_page_n_updates_page_n_not_page_0 — asserts-mock — kept page_idx + page0 preservation assertions (storage observables); docstring updated
- [x] tests/test_routes_pages.py::TestPostPageRerun::test_rerun_awaits_run_stage_non_blocking — asserts-mock — replaced with test_rerun_uses_spec_engine_by_default + test_rerun_with_explicit_engine_returns_200
- [x] tests/test_routes_pages.py::TestPostPageRerun::test_rerun_updates_page_state — asserts-mock — retargeted: assert GET text after rerun (observable); added test_rerun_nonexistent_page_returns_404
- [x] tests/test_routes_prefs.py::TestGetPrefs::test_returns_default_prefs — no-bad-case — added test_returns_default_prefs_when_adapter_has_no_app_data (bad: empty adapter → all defaults)
- [x] tests/test_routes_prefs.py::TestGetPrefs::test_returns_stored_prefs — no-bad-case — added test_returns_defaults_for_partial_stored_prefs (bad: partial prefs → unset fields use defaults)
- [x] tests/test_routes_prefs.py::TestGetPrefs::test_returns_defaults_when_no_adapter — no-bad-case — adapter=None is itself the edge case; accepted as-is
- [x] tests/test_routes_prefs.py::TestPutPrefs::test_saves_prefs — no-bad-case — added test_put_invalid_prefs_returns_422 (bad: invalid field types → 422)
- [x] tests/test_routes_prefs.py::TestPutPrefs::test_write_app_called_with_app_id — asserts-mock — retargeted: assert response body echoes submitted values (observable)
- [x] tests/test_routes_prefs.py::TestPutPrefs::test_put_no_adapter_returns_200 — no-bad-case — no bad case; accepted as-is
- [x] tests/test_routes_prefs.py::TestPutPrefs::test_put_ui_prefs_subset — no-bad-case — added test_put_ui_prefs_with_unknown_fields_returns_200 (bad: extra fields accepted without 422)
- [x] tests/test_routes_prefs.py::TestPutPrefs::test_put_ui_prefs_persists_via_adapter — asserts-mock — retargeted: assert response body contains the submitted ui_prefs values (observable)
- [x] tests/test_smoke.py::test_import — no-bad-case — import smoke only; no bad case possible; accepted as-is
- [x] tests/test_storage.py::TestGetProjectDir::test_returns_path_under_root — no-bad-case — added test_falls_back_to_default_when_env_unset (bad: env unset → default root used, not crash)
- [x] tests/test_storage.py::TestWriteTxt::test_write_txt — no-bad-case — added test_write_txt_out_of_range_raises (bad: page index 99 → FileNotFoundError)
- [x] tests/test_storage.py::TestWriteCombinedTxt::test_combined_txt_concatenates — no-bad-case — added test_combined_txt_with_empty_page_text (bad: empty page text → non-empty pages still appear)
- [x] tests/test_storage.py::TestListProjects::test_empty_when_no_projects — no-bad-case — added test_corrupt_project_json_is_skipped_gracefully (bad: invalid JSON skipped; valid project still listed)
- [x] tests/test_storage.py::TestListProjects::test_lists_written_projects — no-bad-case — added test_multiple_projects_returned_in_stable_order (bad: 3 projects → stable sorted order)
- [x] tests/test_suite.py::TestSuiteJson::test_pd_suite_json_exists — no-bad-case — json structure test; accepted as-is
- [x] tests/test_suite.py::TestSuiteJson::test_pd_suite_json_has_required_fields — no-bad-case — subset check; accepted as-is
- [x] tests/test_suite.py::TestSuiteRoutes::test_suite_installed_endpoint_responds — no-bad-case — added test_suite_installed_endpoint_returns_list_of_objects (bad: each entry has app_id)
- [x] tests/test_suite.py::TestSuiteRoutes::test_suite_prefs_endpoint_responds — no-bad-case — added test_suite_prefs_endpoint_returns_object (bad: returns dict not list)
- [x] tests/test_suite.py::TestSuiteRoutes::test_healthz_endpoint_responds — no-bad-case — added test_healthz_bad_method_returns_405 (bad: POST /healthz → 405)
- [x] tests/test_suite.py::TestRegisterSelf::test_bootstrap_spa_used_in_main — tautological — replaced with test_bootstrap_spa_invoked_on_startup (behavioral: call_count=1 after main())
- [x] tests/test_suite.py::TestRegisterSelf::test_register_self_is_importable — no-bad-case — added test_register_self_does_not_raise_on_call (bad: callable executes without crash)
- [x] tests/test_suite.py::TestCLIFlags::test_unregister_suite_flag_exists — tautological — replaced with test_unregister_suite_flag_in_help + test_unregister_suite_flag_exits_without_launching_server
- [x] tests/test_suite.py::TestCLIFlags::test_install_desktop_shortcut_flag_exists — tautological — replaced with test_install_desktop_shortcut_flag_in_help + test_install_desktop_shortcut_raises_not_implemented
- [x] tests/test_suite.py::TestCLIFlags::test_remove_desktop_shortcut_flag_exists — tautological — replaced with test_remove_desktop_shortcut_flag_in_help + test_remove_desktop_shortcut_raises_not_implemented
- [x] tests/test_words_route.py::test_words_payload_shape — asserts-mock — replaced with real storage round-trip via `_seed_project_with_words`
- [x] tests/test_words_route.py::test_words_missing_returns_404 — asserts-mock — replaced with real missing-project sidecar on disk
- [x] tests/smoke/test_e2e.py::test_e2e_job_completes — no-bad-case — no bad case for e2e smoke; accepted as-is (xfails without weights; marker retained)
- [x] frontend/src/App.test.tsx::App::renders without crashing and shows home page at / — no-bad-case — bad case: unknown route → shell renders without crash, no home-page testid — sibling added
- [x] frontend/src/App.test.tsx::App::AppShell mock receives a main prop — no-bad-case — structural prop-passing; accepted as-is
- [x] frontend/src/api/useOcrJob.test.tsx::useOcrJob::starts idle with no job data when jobId is null — no-bad-case — null jobId is the edge case; accepted as-is
- [x] frontend/src/api/useOcrJob.test.tsx::useOcrJob::exposes progress as fraction of pages_done / page_count — no-bad-case — bad case: page_count=0 → progress=null (division-by-zero guard) — sibling added
- [x] frontend/src/api/useOcrJob.test.tsx::useOcrJob::surfaces extra fields (output_dir, output_mode, pages, name) via jobData — no-bad-case — bad case: API omits optional fields → jobData fields are undefined (no crash) — sibling added
- [x] frontend/src/api/useOcrJob.test.tsx::useOcrJob::stops polling when state reaches succeeded — no-bad-case — bad case: network error during poll → status=error, jobData=null — sibling added
- [x] frontend/src/api/useOcrJob.test.tsx::useOcrJob::resets to idle when jobId changes to null — no-bad-case — lifecycle assertion; accepted as-is
- [x] frontend/src/api/useOcrJob.test.tsx::useOcrJob::uses the default fetch when fetchFn is not provided (stub) — no-bad-case — stub; accepted as-is (no meaningful bad case)
- [x] frontend/src/components/JobConfigInline.test.tsx::defaultProjectName::returns basename for path source — no-bad-case — added test for empty path → returns "ocr-job" fallback
- [x] frontend/src/components/JobConfigInline.test.tsx::defaultProjectName::returns ocr-job-short for upload source — no-bad-case — no bad case; accepted as format assertion
- [x] frontend/src/components/JobConfigInline.test.tsx::JobConfigInline::renders all required form fields — no-bad-case — no bad case; accepted as render smoke
- [x] frontend/src/components/JobConfigInline.test.tsx::JobConfigInline::pre-fills project name from source basename — no-bad-case — no bad case; accepted as pre-fill assertion
- [x] frontend/src/components/JobConfigInline.test.tsx::JobConfigInline::pre-fills project name as ocr-job-short for uploads — no-bad-case — no bad case; accepted as pre-fill assertion
- [x] frontend/src/components/JobConfigInline.test.tsx::JobConfigInline::does NOT render a separate output-dir field — no-bad-case — absence assertion; no bad case possible; accepted as-is
- [x] frontend/src/components/JobConfigInline.test.tsx::JobConfigInline::calls onCancel when 'Use different files' is clicked — no-bad-case — no bad case; accepted as callback assertion
- [x] frontend/src/components/RecentProjectsList.test.tsx::RecentProjectsList::shows 'No recent projects' when prefs has empty list — no-bad-case — empty-list edge case; error path covered by existing 'shows empty state when fetch fails'; accepted as-is
- [x] frontend/src/components/__tests__/OutputConfigPanel.test.tsx::emits change when path is typed in specified mode — no-bad-case — added test for clearing path (empty string onChange)
- [x] frontend/src/components/__tests__/SourcePicker.test.tsx::calls onUploadComplete for a dropped file — no-bad-case — added test: upload error shown + onUploadComplete not called; also fixed component to catch and surface upload errors
- [x] frontend/src/components/__tests__/SourcePicker.test.tsx::dropzone has a generous min-height — no-bad-case — layout test; no bad case possible; accepted as-is
- [x] frontend/src/components/__tests__/SourcePicker.test.tsx::emits onPathChosen for path input — no-bad-case — added test for empty path not emitting onPathChosen
- [x] frontend/src/components/__tests__/SourcePicker.test.tsx::clicking the dropzone triggers the hidden file input — no-bad-case — no bad case; accepted as interaction assertion
- [x] frontend/src/components/__tests__/SourcePicker.test.tsx::pressing Enter on the dropzone triggers the file input — no-bad-case — no bad case; accepted as keyboard assertion
- [x] frontend/src/components/__tests__/SourcePicker.test.tsx::renders the dropped filename after a drop — no-bad-case — no bad case; accepted as state assertion
- [x] frontend/src/components/__tests__/SourcePicker.test.tsx::lists every dropped file with a count header — no-bad-case — added test for zero files → no chosen state shown
- [x] frontend/src/components/__tests__/SourcePicker.test.tsx::clear button resets the display and fires onClear — no-bad-case — no bad case; accepted as interaction assertion
- [x] frontend/src/components/__tests__/SourcePicker.test.tsx::clicking the clear button does not re-open the file picker — no-bad-case — no bad case; accepted as event-propagation assertion
- [x] frontend/src/pages/PageViewPage.test.tsx::PageViewPage::renders canvas with correct image src — no-bad-case — added: shows empty textarea when page data has no text (blank page result)
- [x] frontend/src/pages/PageViewPage.test.tsx::PageViewPage::renders textarea with page OCR text — no-bad-case — bad case: empty OCR text (blank page result) — sibling added
- [x] frontend/src/pages/PageViewPage.test.tsx::PageViewPage::save button calls PUT /api/pages/:id/:idx/text — no-bad-case — bad case: save failure shows error toast — sibling added
- [x] frontend/src/pages/PageViewPage.test.tsx::PageViewPage::shows success toast after save — no-bad-case — bad case: error toast on save failure — covered by sibling above
- [x] frontend/src/pages/PageViewPage.test.tsx::PageViewPage::re-run page trigger button is rendered — no-bad-case — bad case: rerun buttons disabled while rerun is in-progress — sibling added
- [x] frontend/src/pages/PageViewPage.test.tsx::PageViewPage::DocTR menu item calls POST /api/pages/:id/:idx/rerun with engine doctr — no-bad-case — bad case: error toast when POST 500 — sibling added
- [x] frontend/src/pages/PageViewPage.test.tsx::PageViewPage::Tesseract menu item calls POST with engine tesseract — no-bad-case — bad case: error toast when POST 500 — sibling added
- [x] frontend/src/pages/PageViewPage.test.tsx::PageViewPage::textarea updates after rerun completes — no-bad-case — bad case: textarea unchanged after failed rerun — sibling added
- [x] frontend/src/pages/__tests__/PageViewPage.test.tsx::passes fetched words to PageImageCanvas — duplicate — resolved: M3 merged both files into __tests__/PageViewPage.test.tsx; no separate co-located file exists
- [x] frontend/src/pages/__tests__/PageViewPage.test.tsx::renders zoom toolbar with +/-/Fit/100% buttons — duplicate — resolved: M3 merged both files; tests live in merged __tests__/PageViewPage.test.tsx
- [x] frontend/src/pages/__tests__/PageViewPage.test.tsx::Fit returns the viewer to auto-fit after zooming in — duplicate — resolved: M3 merged; unique word-overlay cases now in merged file
- [x] frontend/src/pages/__tests__/PageViewPage.test.tsx::100% sets zoom to native 1.0 — duplicate — resolved: M3 merged; unique word-overlay cases now in merged file
- [x] frontend/src/pages/__tests__/PageViewPage.test.tsx::renders canvas with zero words when words fetch fails — duplicate — resolved: M3 merged; test retained in merged file
- [x] frontend/src/pages/ResultsPage.test.tsx::ResultsPage::renders project name after load — no-bad-case — bad case: error alert on fetch failure, project name absent — sibling added
- [x] frontend/src/pages/ResultsPage.test.tsx::ResultsPage::renders page rows in done state — no-bad-case — bad case: no page-rows when page list is empty — sibling added
- [x] frontend/src/pages/ResultsPage.test.tsx::ResultsPage::page rows have data-testid='page-row' for Playwright targeting — no-bad-case — structural assertion; accepted as-is (no meaningful bad case)
- [x] frontend/src/pages/ResultsPage.test.tsx::ResultsPage::shows text preview — no-bad-case — bad case: em-dash shown when text_preview is empty string — sibling added
- [x] frontend/src/pages/ResultsPage.test.tsx::ResultsPage::navigates to page view when row is clicked — no-bad-case — bad case: no page-rows present during loading state — sibling added
- [x] frontend/src/pages/ResultsPage.test.tsx::ResultsPage::re-run all button sends POST /api/jobs/:id/rerun — no-bad-case — bad case: rerun POST non-ok doesn't crash; page still shows — sibling added
- [x] frontend/src/pages/ResultsPage.test.tsx::ResultsPage::re-run all button re-fetches job status on success — no-bad-case — bad case: re-fetch failure after rerun shows error alert — sibling added
- [x] frontend/src/pages/__tests__/HomePage.test.tsx::local + containerized shows drop zone and path input — no-bad-case — no bad case; layout variant; accepted as-is
- [x] frontend/src/pages/__tests__/HomePage.test.tsx::local + not containerized shows drop, file pick, and path together — no-bad-case — no bad case; layout variant; accepted as-is
- [x] frontend/src/pages/__tests__/HomePage.test.tsx::managed shows upload-only (no path input) — no-bad-case — no bad case; layout variant; accepted as-is
- [x] frontend/src/pages/__tests__/HomePage.test.tsx::JobConfigInline is hidden until a source is chosen — no-bad-case — no bad case; conditional render assertion; accepted as-is
- [x] frontend/src/pages/__tests__/HomePage.test.tsx::JobConfigInline appears after a path is chosen, and clears on cancel — no-bad-case — no bad case; state transition assertion; accepted as-is
- [x] frontend/src/runtime/__tests__/ConfigContext.test.tsx::fetches /api/config on mount — no-bad-case — bad cases: non-ok response + network error both keep cfg=null (loading state); no crash — siblings added
