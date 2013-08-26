
/*
    ============================================================================
    === module with CRUD functionality for comments ============================
    ============================================================================
*/

/*
    remove wysiwyg editor
*/
function close_wysiwyg(id){
    CKEDITOR.instances['comment-wysiwyg-' + id].destroy();
    jQuery(".comment-action-buttons").hide();
    jQuery(".comment-edit-button").show();

    var content = jQuery("#comment-wysiwyg-" + id);
    content
        .removeAttr("contenteditable")
        .empty()
        .html(content.data("old_content"));
}

/*
    create wysiwyg editor for element with selector
*/
function create_wysiwyg(selector){
    var inline = jQuery("#" + selector);

    var content = jQuery("#" + selector);
    content.data("old_content", content.html());

    if (!inline.hasClass("cke_editable")){
        init_wysiwyg(selector);
    }
}

/*
    recount post numbers
*/
function recount_comments(id){
    var len = jQuery(".js-comment-" + id).length;
    var wrap = jQuery("#js-comments-count-" + id);
    if (len === 0){
        wrap.hide();
    } else {
        wrap.show();
    }
    // TODO doesn't solve i18n correctly - one item, <5 items, >=5 items
    title = wrap.find("span").html();
    title_arr = title.split(" ");
    title_arr[0] = len;
    title = title_arr.join(" ");
    wrap.find("span").html(title);
}

/*
    === bind all ===============================================================
*/

jQuery(document).ready(function(){

    /*
        delete comment handler
    */

    jQuery(".comments").on("click", ".js-delete-comment", function(e){
        if (confirm(jQuery(this).data("confirm"))){
            var pk = jQuery(this).data("comment_pk");
            var post_pk = jQuery(this).data("post_pk");
            jQuery.post(
                jQuery(this).attr("href"),
                {comment_id: pk},
                function(data, textStatus, jqXHR){
                    jQuery("#comment-" + pk).remove();
                    recount_comments(post_pk);
                }
            );
        }
        e.preventDefault();
    });

    /*
        create wysiwyg
    */
    jQuery(".comments").on("click", ".js-edit-comment", function(){

        var comment_id = jQuery(this).data("comment_id");
        var wrapper = jQuery("#comment-" + comment_id);
        var selector = 'comment-wysiwyg-' + comment_id;
        var inline = jQuery("#" + selector);

        // enable editing with html5
        inline.attr("contenteditable", "true");

        create_wysiwyg(selector);

        // show wysiwyg
        inline.show();

        // toggle buttons
        wrapper.find(".comment-action-buttons").show();
        wrapper.find(".comment-edit-button").hide();

    });

    /*
        store new html
    */
    jQuery(".comments").on("click", ".js-store-wysiwyg", function(e){
        var save_element = jQuery(this);
        var comment_id = save_element.data("comment_id");
        var new_html = CKEDITOR.instances['comment-wysiwyg-' + comment_id].getData();
        var post_id = save_element.data("post_id");
        var container_id = save_element.data("container_id");

        jQuery.post(
            save_element.data("service_url"),
            {
                comment: new_html,
                comment_id: comment_id,
                post_type: save_element.data("post_type"),
                post_id: post_id
            },
            function(data, textStatus, jqXHR){

                if (data["errors"]){
                    showMessage(
                        jQuery("#comment-wysiwyg-" + comment_id),
                        data["errors"],
                        "after"
                    );
                    return false;
                }

                close_wysiwyg(comment_id);
                jQuery("#comment-wysiwyg-" + comment_id).html("");

                // show new comment
                if (Boolean(save_element.data("clean_container"))){
                    $("#" + container_id).empty();
                }
                $("#" + container_id).show().append(data["html"]);
                recount_comments(post_id);
            }
        );
        e.preventDefault();
        return false;
    });

    /*
        cancel editing comment
    */
    jQuery(".comments").on("click", ".js-cancel-wysiwyg", function(){
        close_wysiwyg(jQuery(this).data("comment_id"));
    });

});
