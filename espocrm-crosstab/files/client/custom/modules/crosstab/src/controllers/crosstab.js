define('crosstab:controllers/crosstab', ['controller'], function (Dep) {

    return Dep.extend({

        defaultAction: 'index',

        checkAccess: function () {
            return this.getAcl().check('Crosstab');
        },

        actionIndex: function () {
            this.main('crosstab:views/crosstab/index', {});
        },
    });
});
