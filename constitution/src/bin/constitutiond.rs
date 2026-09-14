use iron_constitution::invariants::RiskParameters;
use iron_constitution::ipc::MAX_FRAME_BYTES;
use iron_constitution::{ConstitutionService, ipc::IpcServer};
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::thread;

const DEFAULT_BIND: &str = "127.0.0.1:15565";

fn main() {
    let listener = TcpListener::bind(DEFAULT_BIND).expect("failed to bind constitutiond");
    eprintln!("[constitutiond] Iron Constitution listening on {DEFAULT_BIND}");

    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                thread::spawn(move || {
                    let service = ConstitutionService::new(RiskParameters::default());
                    let mut server = IpcServer::new(service);
                    let _ = handle_connection(stream, &mut server);
                });
            }
            Err(e) => eprintln!("[constitutiond] accept error: {e}"),
        }
    }
}

fn handle_connection(mut stream: TcpStream, server: &mut IpcServer) -> std::io::Result<()> {
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

        let response = server.handle_frame(&frame);
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