use iron_constitution::invariants::RiskParameters;
use iron_constitution::ipc::{IpcError, IpcServer, MAX_FRAME_BYTES};
use iron_constitution::ConstitutionService;
use std::io::{Read, Write};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let json_payload = if args.len() > 1 {
        args[1..].join(" ")
    } else {
        let mut stdin_buf = String::new();
        std::io::stdin()
            .read_to_string(&mut stdin_buf)
            .expect("failed to read JSON payload from stdin");
        stdin_buf
    };

    let frame = json_payload.trim();

    if !frame.is_empty() && frame.len() > MAX_FRAME_BYTES {
        eprintln!("Payload exceeds MAX_FRAME_BYTES = {MAX_FRAME_BYTES}");
        std::process::exit(1);
    }

    let service = ConstitutionService::new(RiskParameters::default());
    let mut server = IpcServer::new(service);

    let response = if frame.is_empty() {
        let hb = serde_json::json!({
            "protocol_version": iron_constitution::ipc::IPC_PROTOCOL_VERSION,
            "alive": true,
            "usage": "constitution_cli '<envelope-json>' | constitution_cli",
        });
        serde_json::to_string(&hb).expect("serialize heartbeat")
    } else {
        match server.handle_frame(frame.as_bytes()) {
            Ok(resp) => resp,
            Err(IpcError::VersionMismatch { .. }) => {
                serde_json::json!({ "error": "version_mismatch" }).to_string()
            }
            Err(e) => serde_json::json!({ "error": e.to_string() }).to_string(),
        }
    };

    let stdout = std::io::stdout();
    let mut lock = stdout.lock();
    writeln!(lock, "{response}").expect("failed to write verdict to stdout");
}
