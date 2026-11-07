# CAD-GIT

A local CAD versioning tool with a Rust core and OpenUSD scene interchange.
It preserves native snapshots, records how shapes change between saved states,
and provides visual comparison and conflict resolution. Rhino and Blender are
the first application adapters; the plugin model supports additional tools.
It starts from the command line and works without AI agents or a remote service.

The project is in specification/prototype development. See the
[full v0.1 specification](docs/SPECIFICATION.md) for the proposed behavior,
storage format, CLI, MCP interface, and acceptance criteria. The `test/` folder
contains an earlier exchange smoke test; its draft config predates this spec.

## License

This project is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE).

Use, modification, and distribution are permitted for the purposes specified in
the license, including noncommercial purposes. Commercial uses outside those
permissions require a separate license from the copyright holder.

This is source-available software. The license does not require disclosure of
source code for distributed modifications. See [LICENSE](LICENSE) for the full
terms.
