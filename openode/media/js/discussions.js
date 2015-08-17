
jQuery(".js-discussion-reaction").on("click", function(e){
    // reply to function
    CKEDITOR.instances["id_text"].insertElement(
        CKEDITOR.dom.element.createFromHtml(
            jQuery(this).data("html")
        )
    );
    e.preventDefault();
});

jQuery(document).ready(function(){
    jQuery(".js-post-preview").each(function(index, element){

        jQuery(element).qtip({
            overwrite: false,
            content: {
                text: "loading",
                ajax: {
                    url: jQuery(element).data("post_url"),
                    type: "GET"
                }
            },
            position: {
                target: 'mouse',
                viewport: jQuery(window),
                adjust: {
                    method: 'shift shift',
                    x: 10,
                    y: 10
                }
            },
            show: {
                delay: 250,
                effect: false
            },
            hide: {
                fixed: true,
                delay: 0,
                effect: false
            },
            style: {
                classes: 'ui-tooltip-reply-preview',
                tip: {
                    width: 10,
                    height: 5,
                    mimic: 'center',
                    offset: 15
                }
            }
        });

    });
});
