use rusqlite::{Connection, params};
use serde_json::{Value, json};
use tauri::Manager;

fn connection(app: &tauri::AppHandle) -> Result<Connection, String> {
    let dir = app.path().app_data_dir().map_err(|e|e.to_string())?;
    std::fs::create_dir_all(&dir).map_err(|e|e.to_string())?;
    let db = Connection::open(dir.join("application.sqlite")).map_err(|e|e.to_string())?;
    db.busy_timeout(std::time::Duration::from_secs(5)).map_err(|e|e.to_string())?;
    db.execute_batch("PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS metadata(id INTEGER PRIMARY KEY, value TEXT NOT NULL); CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, entity TEXT NOT NULL, value TEXT NOT NULL); CREATE INDEX IF NOT EXISTS records_entity ON records(entity);").map_err(|e|e.to_string())?;
    Ok(db)
}

fn rows(db: &Connection, entity: Option<&str>) -> Result<Vec<Value>, String> {
    let mut stmt = db.prepare("SELECT value FROM records WHERE (?1 IS NULL OR entity = ?1)").map_err(|e|e.to_string())?;
    let values = stmt.query_map(params![entity], |r|r.get::<_,String>(0)).map_err(|e|e.to_string())?;
    values.map(|v|serde_json::from_str(&v.map_err(|e|e.to_string())?).map_err(|e|e.to_string())).collect()
}

#[tauri::command]
fn read_state(app: tauri::AppHandle) -> Result<Value, String> {
    let db=connection(&app)?;
    let text=db.query_row("SELECT value FROM metadata WHERE id=1",[],|r|r.get::<_,String>(0)).unwrap_or("{\"revision\":0}".into());
    let meta:Value=serde_json::from_str(&text).map_err(|e|e.to_string())?;
    Ok(json!({"meta":meta,"records":rows(&db,None)?}))
}

#[tauri::command]
fn list_records(app: tauri::AppHandle, entity: String) -> Result<Vec<Value>, String> {
    rows(&connection(&app)?,Some(&entity))
}

#[tauri::command]
fn write_state(app: tauri::AppHandle, state: Value, expected: i64) -> Result<(), String> {
    if state.to_string().len()>20*1024*1024 {return Err("Local database size limit exceeded.".into());}
    let records=state["records"].as_array().ok_or("Invalid records")?;
    if records.len()>10000 {return Err("Record limit exceeded.".into());}
    let mut db=connection(&app)?;
    let tx=db.transaction_with_behavior(rusqlite::TransactionBehavior::Immediate).map_err(|e|e.to_string())?;
    let text=tx.query_row("SELECT value FROM metadata WHERE id=1",[],|r|r.get::<_,String>(0)).unwrap_or("{\"revision\":0}".into());
    let meta:Value=serde_json::from_str(&text).map_err(|e|e.to_string())?;
    if meta["revision"].as_i64().unwrap_or(0)!=expected || state["meta"]["revision"].as_i64()!=Some(expected+1) {return Err("Another window changed these records. Reload and retry.".into());}
    tx.execute("DELETE FROM records",[]).map_err(|e|e.to_string())?;
    for record in records {
        let id=record["id"].as_str().ok_or("Invalid ID")?;
        let entity=record["entity"].as_str().ok_or("Invalid module")?;
        tx.execute("INSERT INTO records(id,entity,value) VALUES(?1,?2,?3)",params![id,entity,record.to_string()]).map_err(|e|e.to_string())?;
    }
    tx.execute("INSERT OR REPLACE INTO metadata(id,value) VALUES(1,?1)",[state["meta"].to_string()]).map_err(|e|e.to_string())?;
    tx.commit().map_err(|e|e.to_string())
}

#[tauri::command]
async fn export_backup(app: tauri::AppHandle, contents: String) -> Result<String, String> {
    use tauri_plugin_dialog::DialogExt;
    if contents.len()>20*1024*1024 {return Err("Backup exceeds the size limit.".into());}
    #[cfg(desktop)]
    {
        let path=app.dialog().file().add_filter("JSON backup",&["json"]).set_file_name("application-backup.json").blocking_save_file().ok_or("Export cancelled")?;
        let path=path.into_path().map_err(|e|e.to_string())?;
        std::fs::write(&path,contents).map_err(|e|e.to_string())?;
        return Ok(path.display().to_string());
    }
    #[cfg(mobile)]
    {
        use tauri_plugin_fs::FsExt;
        let path=app.dialog().file().add_filter("JSON backup",&["json"]).set_file_name("application-backup.json").blocking_save_file().ok_or("Export cancelled")?;
        let mut file=app.fs().open(path,tauri_plugin_fs::OpenOptions::new().write(true).create(true).truncate(true)).map_err(|e|e.to_string())?;
        use std::io::Write;
        file.write_all(contents.as_bytes()).map_err(|e|e.to_string())?;
        return Ok("Backup saved".into());
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![read_state,list_records,write_state,export_backup])
        .run(tauri::generate_context!())
        .expect("Application runtime failed");
}
