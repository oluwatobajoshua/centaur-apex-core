use iron_constitution::invariants::RiskParameters;
use iron_constitution::ipc::{IpcServer, MAX_FRAME_BYTES};
use iron_constitution::ConstitutionService;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::{Arc, Mutex};
use std::thread;

fn resolve_bind_address() -> String {
    let host = std::env::var("CONSTITUTION_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port = std::env::var("CONSTITUTION_PORT")
        .ok()
        .and_then(|p| p.parse::<u16>().ok())
        .unwrap_or(15565);
    format!("{host}:{port}")
}

fn main() {
    // Single Constitution kernel for the daemon's lifetime, shared across all
    // TCP connections so kernel state (FSM, verdict history) is persistent.
    let server = Arc::new(Mutex::new(IpcServer::new(ConstitutionService::new(
        RiskParameters::from_env_or_default(),
    ))));

    let bind_addr = resolve_bind_address();
    let listener = TcpListener::bind(&bind_addr).unwrap_or_else(|e| {
        eprintln!("[constitutiond] failed to bind {bind_addr}: {e}");
        std::process::exit(1);
    });
    eprintln!("[constitutiond] Iron Constitution listening on {bind_addr}");

    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                let server = Arc::clone(&server);
                thread::spawn(move || {
                    let _ = handle_connection(stream, &server);
                });
            }
            Err(e) => eprintln!("[constitutiond] accept error: {e}"),
        }
    }
}

fn handle_connection(mut stream: TcpStream, server: &Arc<Mutex<IpcServer>>) -> std::io::Result<()> {
    let mut header = [0u8; 4];
    loop {
        let n = read_full(&mut stream, &mut header)?;
        if n == 0 {
            return Ok(());
        }
        let frame_len = u32::from_be_bytes(header) as usize;
        if frame_len == 0 || frame_len > MAX_FRAME_BYTES {
            eprintln!("[constitutiond] invalid frame length {frame_len}");
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "invalid frame length",
            ));
        }
        let mut frame = vec![0u8; frame_len];
        read_full(&mut stream, &mut frame)?;

        // Lock per frame: one in-flight evaluation, persistent kernel state.
        let response = server
            .lock()
            .expect("constitution kernel poisoned")
            .handle_frame(&frame);
        match response {
            Ok(resp) => {
                write_frame(&mut stream, resp.as_bytes())?;
            }
            Err(e) => {
                let err_payload = serde_json::json!({ "error": e.to_string() }).to_string();
                write_frame(&mut stream, err_payload.as_bytes())?;
            }
        }
    }
}

fn read_full(stream: &mut TcpStream, buf: &mut [u8]) -> std::io::Result<usize> {
    let mut read = 0usize;
    while read < buf.len() {
        let n = stream.read(&mut buf[read..])?;
        if n == 0 {
            break;
        }
        read += n;
    }
    Ok(read)
}

fn write_frame(stream: &mut TcpStream, payload: &[u8]) -> std::io::Result<()> {
    let len = (payload.len() as u32).to_be_bytes();
    stream.write_all(&len)?;
    stream.write_all(payload)?;
    stream.flush()
}
