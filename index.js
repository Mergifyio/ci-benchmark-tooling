const ciRunnersDatasFilePath = "./runner_prices.csv"


function displayDefaultCsvData() {
    var csvFileText = null;

    var req = new XMLHttpRequest();
    req.onreadystatechange = function(){
        if(req.status == 200 && req.readyState == 4){
            csvFileText = req.responseText;
            var csvData = csvFileText.trim().split("\n");

            var tbodyDom = document.getElementById("csvTable").getElementsByTagName("tbody")[0];

            for (var row = 1; row < csvData.length; row++) {
                var newRow = tbodyDom.insertRow();
                var csvLineArray = csvData[row].split(";");
                for (var col = 0; col < csvLineArray.length; col++) {
                    var newCell = newRow.insertCell();
                    newCell.innerHTML = csvLineArray[col];
                }
                // Cell for "Cost for the specified number of minutes"
                var newCell = newRow.insertCell();
                newCell.innerHTML = "0";
                newCell.setAttribute("data-default-price", csvLineArray[csvLineArray.length-1]);
                newCell.setAttribute("class", "price-cell");
            }
        }
    };

    req.open("GET", ciRunnersDatasFilePath, true);
    req.send();

}

function calculate(minutes) {
    if (isNaN(minutes)) {
        alert("Please enter only numbers");
        return;
    }

    var priceCells = document.getElementsByClassName("price-cell");
    for (var i = 0 ; i < priceCells.length ; i++) {
        priceCells[i].innerHTML = Number(priceCells[i].getAttribute("data-default-price")) * minutes;
    }
}
