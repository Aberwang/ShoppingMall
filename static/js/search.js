
function search_click(){
    var keywords = $('#search_keywords').val()

    if(keywords == ""){
        return
    }
    request_url = "/search/1?keywords="+keywords;
    window.location.href = request_url
}

$('#jsSearchBtn').on('click',function(){
        search_click()
    });
