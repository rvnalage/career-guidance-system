import { useEffect } from "react";
import { createPortal } from "react-dom";

function ConfirmModal({
    open,
    title,
    message,
    confirmLabel = "Confirm",
    cancelLabel = "Cancel",
    onConfirm,
    onCancel,
}) {
    useEffect(() => {
        if (!open) {
            return undefined;
        }

        const previousOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";

        const handleEscape = (event) => {
            if (event.key === "Escape") {
                onCancel();
            }
        };

        window.addEventListener("keydown", handleEscape);

        return () => {
            document.body.style.overflow = previousOverflow;
            window.removeEventListener("keydown", handleEscape);
        };
    }, [open, onCancel]);

    if (!open) {
        return null;
    }

    return createPortal(
        <div className="modal-backdrop" role="presentation" onClick={onCancel}>
            <div className="modal-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-modal-title" onClick={(event) => event.stopPropagation()}>
                <h3 id="confirm-modal-title">{title}</h3>
                <p>{message}</p>
                <div className="confirm-panel-actions">
                    <button className="button" type="button" onClick={onConfirm}>
                        {confirmLabel}
                    </button>
                    <button className="button secondary" type="button" onClick={onCancel}>
                        {cancelLabel}
                    </button>
                </div>
            </div>
        </div>,
        document.body,
    );
}

export default ConfirmModal;
