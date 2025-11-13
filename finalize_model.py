# finalize_model.py
import sys
import logging
import os

try:
    # 1. Importa as funções de negócio do script de treino
    #    (load_config é de train_drl_model, e finalize_training também está lá)
    from train_drl_model import load_config, finalize_training
    
    # 2. Importa a função de logging da sua localização correta
    from src.utils.logger import setup_logging
except ImportError as e:
    print(f"Erro de importação: {e}")
    print("Certifique-se de que 'train_drl_model.py' e 'src/utils/logger.py' estão acessíveis.")
    sys.exit(1)

def main():
    """
    Script de finalização independente.
    
    Carrega a configuração e chama *apenas* a função de finalização 
    para promover o melhor checkpoint (ou o último) para produção.
    """
    config_path = 'configs/main.yaml'
    
    try:
        # Configura um log específico para o processo de finalização
        setup_logging(log_file_prefix='finalize_model')
        
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