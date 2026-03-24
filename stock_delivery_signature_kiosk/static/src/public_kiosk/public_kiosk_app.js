import { App, Component, onMounted, onWillStart, onWillUnmount, useState, whenReady } from "@odoo/owl";
import { NameAndSignature } from "@web/core/signature/name_and_signature";
import { MainComponentsContainer } from "@web/core/main_components_container";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { makeEnv, startServices } from "@web/env";
import { getTemplate } from "@web/core/templates";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";

const POLL_INTERVAL = 2000;

class DeliverySignatureKioskApp extends Component {
    static template = "stock_delivery_signature_kiosk.public_kiosk_app";
    static components = {
        MainComponentsContainer,
        NameAndSignature,
    };
    static props = {
        token: { type: String },
        companyId: { type: Number },
        companyName: { type: String },
    };

    setup() {
        this.notification = useService("notification");
        this.state = useState({
            screen: "loading",
            companyLogo: false,
            request: null,
            isSubmitting: false,
            successMessage: "",
            errorMessage: "",
        });
        this.signature = useState({
            name: "",
            isSignatureEmpty: true,
        });
        this.pollHandle = null;
        this.successTimeout = null;

        onWillStart(async () => {
            await this.refreshPendingRequest();
        });

        onMounted(() => {
            this.pollHandle = window.setInterval(() => this.refreshPendingRequest(), POLL_INTERVAL);
        });

        onWillUnmount(() => {
            window.clearInterval(this.pollHandle);
            window.clearTimeout(this.successTimeout);
        });
    }

    get nameAndSignatureProps() {
        return {
            signature: this.signature,
            defaultFont: "",
            displaySignatureRatio: 3,
            signatureType: "signature",
            noInputName: false,
            mode: "draw",
        };
    }

    setRequest(request) {
        this.state.request = request;
        this.state.errorMessage = "";
        this.state.successMessage = "";
        this.state.screen = "sign";
        this.signature.name = request.partner_name || "";
        this.signature.isSignatureEmpty = true;
        this.signature.signatureImage = false;
    }

    clearRequest(nextScreen = "waiting") {
        this.state.request = null;
        this.state.screen = nextScreen;
        this.signature.name = "";
        this.signature.isSignatureEmpty = true;
        this.signature.signatureImage = false;
    }

    async refreshPendingRequest() {
        if (this.state.isSubmitting) {
            return;
        }
        const response = await rpc("/stock_delivery_signature/pending", {
            token: this.props.token,
        });

        if (response.status === "invalid") {
            this.clearRequest("invalid");
            this.state.errorMessage = _t("This kiosk URL is no longer valid.");
            return;
        }

        if (response.status === "idle") {
            if (this.state.screen !== "success") {
                this.clearRequest("waiting");
            }
            return;
        }

        this.state.companyLogo = response.company_logo || false;
        const request = response.request;
        if (!this.state.request || this.state.request.id !== request.id) {
            this.setRequest(request);
            return;
        }
        this.state.request = request;
    }

    async confirmSignature() {
        if (this.state.isSubmitting || this.signature.isSignatureEmpty || !this.state.request) {
            return;
        }

        this.state.isSubmitting = true;
        this.state.errorMessage = "";
        try {
            const response = await rpc("/stock_delivery_signature/sign", {
                token: this.props.token,
                picking_id: this.state.request.id,
                signer_name: this.signature.name || false,
                signature_image: this.signature.getSignatureImage(),
            });
            if (!response.success) {
                this.state.errorMessage = response.error || _t("The signature could not be saved.");
                this.notification.add(this.state.errorMessage, {
                    type: "danger",
                });
                return;
            }

            this.clearRequest("success");
            this.state.successMessage = `${_t("Delivery signed.")} ${response.picking_name}`;
            window.clearTimeout(this.successTimeout);
            const nextRequest = response.next_request || false;
            this.successTimeout = window.setTimeout(() => {
                if (nextRequest) {
                    this.setRequest(nextRequest);
                    return;
                }
                this.state.successMessage = "";
                this.clearRequest("waiting");
            }, nextRequest ? 1200 : 2500);
        } finally {
            this.state.isSubmitting = false;
        }
    }
}

export async function createPublicDeliverySignatureKiosk(document, kioskBackendInfo) {
    await whenReady();
    const env = makeEnv();
    await startServices(env);
    session.server_version_info = kioskBackendInfo.server_version_info;

    const app = new App(DeliverySignatureKioskApp, {
        env,
        getTemplate,
        props: {
            token: kioskBackendInfo.token,
            companyId: kioskBackendInfo.company_id,
            companyName: kioskBackendInfo.company_name,
        },
        dev: env.debug,
        translateFn: _t,
        translatableAttributes: ["data-tooltip"],
    });
    return app.mount(document.body);
}

export default {
    DeliverySignatureKioskApp,
    createPublicDeliverySignatureKiosk,
};
