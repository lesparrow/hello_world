/**
 * Mass action handler "Send Wallet passes" on Contact / Account / Lead lists.
 */
define('wallet-passes:handlers/send-passes', ['action-handler'], (ActionHandler) => {

    return class extends ActionHandler {

        /**
         * @param {{entityType: string, action: string, params: Object}} data
         */
        process(data) {
            this.view.createView('walletSendPasses', 'wallet-passes:views/wallet-pass/modals/send-passes', {
                entityType: data.entityType,
                params: data.params,
            }, view => {
                view.render();

                this.view.listenToOnce(view, 'done', () => {
                    this.view.collection.fetch();
                });
            });
        }
    };
});
