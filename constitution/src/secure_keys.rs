use crate::RiskViolationCode;

#[derive(Clone, Debug, PartialEq)]
pub enum KeyVaultAccess {
    ReadOnly,
    AuthorizedSigner,
    Locked,
}

pub struct SecureKeyManager {
    vault_online: bool,
    access_mode: KeyVaultAccess,
    signing_threshold: u8,
}

impl Default for SecureKeyManager {
    fn default() -> Self {
        Self {
            vault_online: true,
            access_mode: KeyVaultAccess::ReadOnly,
            signing_threshold: 2,
        }
    }
}

impl SecureKeyManager {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn vault_status(&self) -> bool {
        self.vault_online
    }

    pub fn access_mode(&self) -> &KeyVaultAccess {
        &self.access_mode
    }

    pub fn authorize_signing(&mut self, proof_claim: u8) -> Result<(), RiskViolationCode> {
        if !self.vault_online {
            return Err(RiskViolationCode::InvalidNumericalState);
        }
        if proof_claim >= self.signing_threshold {
            self.access_mode = KeyVaultAccess::AuthorizedSigner;
            Ok(())
        } else {
            Err(RiskViolationCode::MaxDrawdownBreached)
        }
    }

    pub fn lock_vault(&mut self) {
        self.vault_online = false;
        self.access_mode = KeyVaultAccess::Locked;
    }

    pub fn fail_safe_liquidation_authorized(&self) -> bool {
        self.access_mode == KeyVaultAccess::AuthorizedSigner
            || self.access_mode == KeyVaultAccess::Locked
    }
}
