/*
    close element box and send request to server if is ajax enabled
*/
function close_element(expander, url){

    if (url){
        jQuery.getJSON(url);
    }

    jQuery(".js-subelement-of-" + expander.data("element_id")).each(function(i, e){
        jQuery(e).hide();
        var expander = jQuery(e).find(".js-expander.js-open").first();
        if (expander.length > 0){
            close_element(expander);
        }

    });
    expander.removeClass("js-open open");
    expander.addClass("js-closed closed");
    jQuery(expander).find(".expander-sign").first().html(expander.data("open"));
}


/*
    open element box and send request to server if is ajax enabled
*/
function open_element(expander, url, animate){

    var element_id = expander.data("element_id");

    if (url){
        jQuery.getJSON(url);
    }

    if (animate) {
        jQuery(".js-subelement-of-" + element_id).slideDown();
    }
    else {
        jQuery(".js-subelement-of-" + element_id).show();
    }
    expander.removeClass("js-closed closed");
    expander.addClass("js-open open");

    //jQuery(expander).find(".expander-sign").first().html(expander.data("close"));
}

/*
    ============================================================================
*/

jQuery(document).ready(function(){

    /*
        bind open/close to click event
    */
    jQuery(".js-expander").on("click", function(e){
        var expander = jQuery(this);
        var use_ajax = expander.hasClass("js-use-ajax");

        e.preventDefault();

        var url;
        if (expander.attr("href") === undefined && expander.attr("href") !== false){
            url = expander.data("url");
        } else {
            url = expander.attr("href");
        }

        if (expander.hasClass("js-closed")){
            open_element(expander, url, true);
        } else {
            close_element(expander, url);
        }
    });

    /*
        initial close of all subelements
    */
    jQuery(".js-subelement").hide();

});
