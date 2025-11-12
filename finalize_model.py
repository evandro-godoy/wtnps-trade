import sys
import logging
import os

# Importa as funções necessárias do script de treino principal
# Assumimos que 'train_drl_model' está no mesmo diretório
try:
    from train_drl_model import load_config, setup_logging, finalize_training
except ImportError:
    print("Erro: Não foi possível encontrar 'train_drl_model.py'.")
    print("Certifique-se de que este script está no mesmo diretório que 'train_drl_model.py'.")
    sys.exit(1)

def main():
    """
    Script de finalização independente.
    
    Carrega a configuração e chama *apenas* a função de finalização 
    para promover o melhor checkpoint (ou o último) para produção.
    """
    config_path = 'configs/main.yaml'
    
    try:
        setup_logging()
        config = load_config(config_path)

        # --- Defina os parâmetros do modelo que você quer finalizar ---
        # (Estes valores devem bater com a configuração 'main.yaml')
        ticker = 'WDO$'
        strategy_name = 'DRLStrategy'
        # -------------------------------------------------------------

        logging.info(f"Iniciando finalização manual para: {ticker} | {strategy_name}")

        finalize_training(
            config=config,
            strategy_name=strategy_name,
            ticker=ticker
        )

        logging.info("Processo de finalização concluído.")

    except Exception as e:
        logging.error(f"Erro fatal durante a finalização: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Limpa os handlers do logging
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)

if __name__ == "__main__":
    main()