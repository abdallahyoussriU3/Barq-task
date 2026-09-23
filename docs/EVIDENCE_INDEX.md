# Evidence and submission index

- Repository URL: https://github.com/abdallahyoussriU3/Barq-task.git
- Final commit: `0080512`
- Matching CI run: not available from this local workspace; GitHub Actions should be run and linked after push.
- Continuous 12-18 minute video URL: pending / not produced in this local environment.
- Challenge receipt ID: not generated in this local workspace.
- Starting video commit: not recorded in this local environment.
- Later documentation-only commits, if any: not applicable for the local verified work in this session.

## Requirement-to-evidence mapping

- Runtime validation: [validate.py](../validate.py) -> commit `0080512` -> local proof: `python validate.py` returned `PASS: all validation checks succeeded`
- Failure and recovery: [failure_test.py](../failure_test.py) -> commit `0080512` -> local proof: `python failure_test.py` returned `PASS: failure and recovery verified; recovered instances=['app-01', 'app-02']`
- PostgreSQL backup/restore: [backup.sh](../backup.sh), [restore.sh](../restore.sh) -> commit `0080512` -> local proof: script execution was run against the live Compose stack; the restore flow is documented in the runtime guide
- CI workflow: [.github/workflows/ci.yml](../.github/workflows/ci.yml) -> commit `0080512`
- Runtime guide: [README.md](../README.md) -> commit `0080512`
- Troubleshooting: [troubleshooting.md](../troubleshooting.md) -> commit `0080512`
- Decisions: [decisions.md](../decisions.md) -> commit `0080512`
- Security review: [security_review.md](../security_review.md) -> commit `0080512`
- AI disclosure: [AI_USAGE.md](../AI_USAGE.md) -> commit `0080512`
- Log analysis: [log_analysis.md](../log_analysis.md) -> commit `0080512`
- Architecture diagram: [docs/ARCHITECTURE.md](ARCHITECTURE.md) plus the generated PNG artifact at the repository root (`architecture.png`) once generated.

## Notes

This evidence set reflects the verified local implementation and runtime proof captured in the workspace. The final submission follow-up would require pushing the repository, generating the GitHub Actions run link, and producing the evidence video against the final three-instance setup on port 8090.
