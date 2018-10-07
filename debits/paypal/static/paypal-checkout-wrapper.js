function debits_render_paypal_button(html_id, mode, create_cb, execute_cb, hash, options, confirmation) {
  hash['processor'] = 'PayPal Checkout';
  var all_options = {
    env: mode, //'sandbox' or 'production'
    payment: function(data, actions) {
      return actions.request.post(create_cb, hash)
        .then(function(res) {
          return res.id;
        });
    },
    onAuthorize: function(data, actions) {
      return actions.request.post(execute_cb, {
        paymentID: data.paymentID,
        payerID:   data.payerID
      })
        .then(function(res) {
          confirmation();
        });
    }
  };
  for(var attrname in options) { all_options[attrname] = options[attrname]; }
  paypal.Button.render(all_options, '#'+html_id);
}