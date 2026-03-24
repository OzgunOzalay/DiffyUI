import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

app.registerExtension({
    name: "DiffyUI.NIfTIPreview.FSLeyes",

    async nodeCreated(node) {
        if (node.comfyClass !== "NIfTIPreview") return;

        node.addWidget("button", "Open in FSLeyes", null, () => {
            const filePath = node._lastNiftiPath;

            if (!filePath) {
                alert("Run the node first — FSLeyes needs the resolved file path from the last execution.");
                return;
            }

            fetch("/diffyui/open_fsleyes", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ file_path: filePath }),
            })
                .then(r => r.json())
                .then(data => {
                    if (data.status !== "ok") {
                        alert("Could not open FSLeyes:\n" + data.error);
                    }
                })
                .catch(err => alert("Request failed:\n" + err));
        }, { serialize: false });
    },

    setup() {
        // Cache the resolved file path on the node whenever it finishes executing.
        api.addEventListener("executed", ({ detail }) => {
            const niftiPaths = detail?.output?.nifti_path;
            if (!niftiPaths?.length) return;

            const node = app.graph.getNodeById(parseInt(detail.node));
            if (node?.comfyClass === "NIfTIPreview") {
                node._lastNiftiPath = niftiPaths[0];
            }
        });
    },
});
